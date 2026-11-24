# Modbus RTU from a PLCnext controller

Proven 2026-11-23 on an AXC F 2152 (firmware 2026.0.2) with an AXL F RS UNI 1H: one device on RS-485, read and
write, a request a second, no errors over an evening. Examples: `examples/rs-uni-modbus` (a probe for any device),
`examples/modbus-rtu-room-sensor` (a complete device with an operator page).

## What it takes

- The controller has no serial port. A serial module on the Axioline bus does it: **AXL F RS UNI 1H** (2688666),
  right of the controller. It is a Modbus RTU **master** only (data sheet 8533).
- Wiring, RS-485 two-wire, connector 2: data + on terminal **10**, data - on **11**. Module at the end of the
  line: bridges **20-30** and **21-31** (built-in termination, which also holds the idle line). Terminals 00 / 01
  stay empty. Shield to a busbar before the module. No answer at all: swap + and -, makers name them differently.
- The device: its own address (1 to 247; **0 is broadcast, nothing answers on it**), baud rate, parity, stop
  bits. Find out how they are set (switches, menu) and whether a change needs a power cycle.

## Steps

1. **Base project with the module** (once per module set-up; `findings.md`, "I/O modules"): in Engineer add the
   module to the controller's Axioline Device List, set on its Parameters page interface type RS-485, protocol
   **Modbus/RTU**, baud rate, data width (e.g. "8 data bits, no parity, 1 stop bit"), data exchange via process
   data; save; `pxproj.py --strip <saved> ~/.plcnext-engineer/base/<NAME>.plcnx2`.
2. **Start from the probe**: copy `examples/rs-uni-modbus`, set `base` in `program.json`, build, write, open the
   page (`pxe.sh hmi`). Choose device address, function and start address with the buttons.
   - "no answer" counting up: wiring, polarity, address, baud rate or parity. The module waits 2.5 s per request.
   - "damaged" counting up: the device answers but with another data width or parity, or two devices answer.
   - "refused" with exception code 2: no register there; code 1: this function is not supported.
   - Values but nonsense: read on.
3. **Find the device's habits** (documents often leave them out; both were unknown for the example device):
   - *Register base*: a list that starts at 1 usually means wire address = number - 1. Check with a value you
     know (a temperature).
   - *32-bit values*: two registers. The probe shows each pair as a float both ways, "high word first" and "low
     word first": one line makes sense. Whole 32-bit numbers may use the other order than floats in the same
     device (seen). Scaled integers (value x 10) need no decoding, only the factor.
4. **Write the real program** from `examples/modbus-rtu-room-sensor/src/MAIN/Code.st`: keep the four steps of the
   exchange, change the list of requests and what is done with each answer.

## The exchange with the module (the part to keep)

The program's ports are the module's 20 bytes each way (`program.json`, `io`): `CTRL_H` command, `CTRL_L` control
bits, `TX01` length, `TX02..` the request without CRC; `STAT_H` command echo, `STAT_L` status bits, `RX01`
length, `RX02..` the answer without CRC.

1. Put the request into `TX..`, the length into `TX01`, the command "transmit" into `CTRL_H` (`16#10`, the next
   time `16#50`: the same command with its toggle bit, or the module does not see a second request).
2. Wait until `STAT_H` echoes the command. Bit 7 of `STAT_H` = the module refused it.
3. Wait for `STAT_L` bit 0 (an answer is there). Bit 2 = no answer in 2.5 s, bit 1 = answer damaged: count it,
   write `16#06` to `CTRL_L` for a few cycles (resets both), start again.
4. Command "read characters" (`16#30` / `16#70`), wait for its echo: the answer is in `RX02..`. `RX03` with bit 7
   set = the device refused (exception), code in `RX04`.

One request at a time, the next one only when the answer or the error is in. In a 100 ms task one exchange takes
about half a second.

## Frames (without CRC, the module adds it)

| Function | Request | Answer |
|---|---|---|
| 03 / 04 read registers | addr, fc, start hi, start lo, 0, quantity | addr, fc, byte count, data (2 per register) |
| 01 read coils | addr, 1, start hi, start lo, 0, quantity | addr, 1, byte count, bits (first coil = bit 0 of the first byte) |
| 16 write registers | addr, 16, start hi, start lo, 0, quantity, byte count, data | addr, 16, start hi, start lo, 0, quantity |
| 05 write one coil | addr, 5, coil hi, coil lo, FF or 00, 00 | the same back |
| 06 write one register | addr, 6, reg hi, reg lo, value hi, value lo | the same back (not every device has it) |

**17 characters per exchange** with this simple way of reading: at most 7 registers per read (3 + 14 bytes) and 5
per write. More in one answer needs the "more to read" bit (bit 7 of `RX01`) and a second "read characters";
not built here. Read long lists in pieces.

## Writing values from an operator page

A value that the device's own keys can change too (a setpoint) is one register with two writers. Pattern in the
example: `X_REQ` (changed by the page's buttons, a whole number), `X_SHADOW` (what was last agreed with the
device). They differ: write `X_REQ` once, then `X_SHADOW := X_REQ`. They are equal when a poll comes in: both
take the device's value. A refused write also sets the shadow, or it is repeated for ever. No write before the
first successful read.

## Floats

No bit cast between DWORD and REAL was found in the tool's Structured Text. `FB_IEEE` (bits to REAL) and
`FB_TOIEEE` (REAL to bits) in the examples compute it. Build the DWORD from the four bytes in the device's word
order first.

## Limits, not tried

Several devices on one line (same code, another address per request); baud rates other than 19200; RS-232 and
RS-422; answers longer than 17 characters; Modbus RTU slave (the module cannot). Modbus TCP is another road,
the firmware's own client: `modbus-tcp.md`.
