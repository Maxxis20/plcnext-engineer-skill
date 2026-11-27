# Virtual PLCnext Control (VPLCNEXT CONTROL 1000 / 2000 / 3000)

The controller as an OCI container on a Linux host instead of a device. Proven 2026-11-27 with VPLCNEXT CONTROL
2000 (x86), image 2026.6.1 (firmware 26.6.1.54), on an Ubuntu Server 24.04 virtual machine with a real-time
kernel, PLCnext Engineer 2026.6: installed, licensed, a project with an operator page written and running
(`examples/spot-price`, unchanged except for the base project and the address). The vendor's own documents: the
user manual "UM EN VIRTUAL PLCNEXT CONTROL" and the application note "Licensing of the Virtual PLCnext Control"
on the product page, and github.com/PLCnext/vplcnextcontrol (install scripts).

## What it needs

- Host: x86-64 or ARM64, Linux with a real-time kernel (`PREEMPT_RT`), podman 4.9 or newer, AppArmor,
  podman-compose 1.4.1. Per instance (2000): 2 cores, 3 GB RAM, 4 GB disk, **2 network interfaces**, one of them
  for the field network only (the container gets a macvlan on it).
- A **licence server**: Wibu CodeMeter Runtime with its network server on, somewhere in the same network.
  It may be another machine. **It must be physical hardware**: the vendor's licence container refuses a virtual
  machine (below). The controller itself may run in a virtual machine.
- PLCnext Engineer 2025.0.2 LTS or newer; it has the device templates.

## Host and container (as done on Ubuntu 24.04)

```bash
sudo apt-get install podman conmon apparmor netavark fuse-overlayfs uidmap acl unzip git
sudo pip3 install --break-system-packages podman-compose==1.4.1
sudo pro attach && sudo pro enable realtime-kernel && sudo reboot      # Ubuntu Pro (free for personal use)
git clone https://github.com/PLCnext/vplcnextcontrol && cd vplcnextcontrol/src
sudo ./CHECK.sh /boot/config-$(uname -r)                               # what the kernel lacks
# container-compose.yml: parent = the field interface, subnet, gateway, ipv4_address, a unique mac_address
sudo ./INSTALL.sh -i /path/without/spaces/vplcnextcontrol2000-x86-64-<version>.tar
```

- The field interface needs no address on the host, only to be up.
- **The image path must not hold spaces.** The product's zip unpacks into a folder with spaces: the script's
  `podman load` then fails ("takes no arguments") and it writes an empty image name into the compose file.
  Copy the tar to a plain name, put the image name back if the first try emptied it.
- The script loads an AppArmor profile, creates the container and a systemd unit (`<project>_vplcnext_1.service`,
  enabled). The host maps the web server to ports 8080 / 8443; on the field address it is 80 / 443.
- First start takes about a minute. The web server inside fails once ("no ssl_certificate is defined") and comes
  up by itself when the firmware has written its HTTPS configuration: do not restart it by hand.
- Inside: `sudo podman exec <container> sh`; the firmware's log is `/opt/plcnext/logs/Arp.log` as on a device.
- Timing: check with `cyclictest` inside the container. On a virtual machine whose host cores are shared, a
  20 s sample gave 9 µs average and one 2.6 ms spike: fine for function tests, not for a 1 ms cycle.

## Licence

- Without a licence the firmware starts, the web management works, and the program does **not** load:
  `No valid license has been found`, `Loading Plc is prevented by 'Arp.System.Lm' because of 'License check'`,
  PLC state `Ready|Blocked`. No demo mode.
- The licence is asked for **when the controller starts**, from the licence server named in
  `/opt/plcnext/config/System/Lm/Lm.config` (`serverHostname`, default `192.168.1.100`; in the web management:
  License management > Configuration). The log shows `License server info: ipAddress=...` when the server is
  found, `ServerNotFound` when not. From the container the host itself is the gateway of its podman network.
- Licence server: install CodeMeter Runtime (`codemeter-lite` is enough: service `codemeter`, tool `cmu`, web
  admin on 127.0.0.1:22352), in `/etc/wibu/CodeMeter/Server.ini` set `IsNetworkServer=1` with the service
  stopped, start it: it listens on 22350 TCP and UDP. Open that port only for the controller's host.
- **Not on a virtual machine**: `cmu -i -f Phoenix_Contact_HW_binding.WibuCmLif` there answers "It is not
  permitted to use this license on a virtual machine, Error 273". On physical hardware the same import works.
  The web depot offers a CmDongle as the other container type (not tried).
- Activation by files, for a server without a browser (manual chapter 8; firm code 6000217). The container file
  is "License Import File.zip" in the product's downloads.
  1. `sudo cmu -i -f Phoenix_Contact_HW_binding.WibuCmLif`, `cmu -l` shows the serial `130-...` (empty container).
  2. `cmu -s <serial> -c 6000217 -f <serial>.WibuCmRaC` (the request).
  3. In a browser anywhere: the vendor's CodeMeter License Central WebDepot, ticket id from the licence
     certificate, "Activate Licenses", container type "CmActLicense ... (HW binding only)", file-based
     transfer, upload the request, download the `.WibuCmRaU`.
  4. `sudo cmu -i -f <serial>.WibuCmRaU`.
  5. The depot then asks for a **receipt**: the command of step 2 again, now made after the import; upload it.
  6. Restart the controller: `A valid license has been found.`, the program loads.
- The licence is then bound to the licence server's hardware. Moving it ("re-hosting") is offered by the depot:
  a request file from the container, the licences are deactivated there, then activated in another container.
  `cmu -x` prints part of the licence's protected data: keep its output out of notes and tickets.
- The ticket id is a credential: it goes into the depot by the owner's hand, not into files or chat.

## Engineer and the skill's scripts

- Base project: start page, section "Virtual Control", tile "VPLCNEXT CONTROL 2000 (x86)" (UI id
  `AID_PCWE_VPLC2000x8600260`); the new project is already a file under
  `%APPDATA%\PHOENIX CONTACT\PLCnext Engineer\<version>\NEW\PROJECT1.plcnx2`; `pxproj.py --strip` it to
  `VPLC2000X86-2026.0`. The template's firmware 2026.0 wrote to a controller with 2026.6.1 without complaint.
- `program.json`: `"base": "VPLC2000X86-2026.0"`, `"target": {"ip": <the container's field address>}`.
  `PLC_HOST` the same address; Engineer reaches the container on the field network (port 41100).
- First connect: the "Secure device login" dialog; `admin` and the vendor's published default password, through
  `pxe-login.sh` from the secret store. Change that password afterwards (web management, User Authentication).
- **The operator page service is off by default** on this controller: the page answers 503 and the REST
  interface does not answer, while the program runs. Switch it on like the other services: web management >
  System Services, or the file `/opt/plcnext/config/System/Scm/Default.scm.config` with
  `<Feature id="EHMI" enable="true"/>` (the file does not exist at first; pattern in `findings.md`, "Service
  switch"), then `systemctl restart plcnext` inside the container.
- After that `pxe.sh open`, `write`, `read`, `set`, `hmi` work as on a device. `pxe.sh write` reports a failure
  on the first write while the page service is still off (its check reads over REST), although the project is
  on the controller.
- Firewall of the controller is on by default; SSH into the container needs its rule in the web management
  (not needed when you can use `podman exec` on the host).

## Not tried

PROFINET through the macvlan, the ARM64 image, the CmDongle, what the controller does when the licence server
goes away while it runs (the config has a renewal interval and a release time), more than one instance on a host.
