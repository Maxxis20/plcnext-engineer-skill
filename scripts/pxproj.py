#!/usr/bin/env python3
"""pxproj.py - build a PLCnext Engineer project file (.plcnx2) from Structured Text sources, without the tool.

A .plcnx2 is a zip: PROJECT.proj (JSON index of every item) + PROJECT/Content/... (one stream per item).
A POU is a folder '<Name>.pou' under 'Logical Elements' with Metadata.meta, Variables.var (declarations as
IEC text), Code.st (body as IEC text) and some empty companions. Tasks and program instances are in
PLCnext/EsmConfiguration.esmc. This script takes an empty project made by the tool (base) and adds to it.

    pxproj.py <program dir> [out.plcnx2]
    pxproj.py --strip <project saved by the tool> <base.plcnx2>     make an empty base project from it

<program dir>/program.json:
    {"name": "MYPROJ", "base": "AXCF2152-2025.6",          (name of a base in the work folder, or a file path)
     "pous": [{"name": "FB_FILTER", "kind": "FunctionBlock"}, ..., {"name": "MAIN", "kind": "Program"}],
     "tasks": [{"name": "Cyclic100", "interval_ms": 100, "instances": [{"name": "M", "program": "MAIN"}]}],
     "target": {"simulation": true}}            (or {"ip": "192.168.1.10"}; left out = as in the base project)
<program dir>/src/<POU>/Variables.var, Code.st

Undocumented format, learned from Engineer 2026.6 files. Ids are derived from names, so a rebuild gives the
same file.
"""
import io, json, os, re, sys, uuid, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True                           # no __pycache__ beside the program's hmi.py

NS = uuid.UUID("6f2d1c0a-51d4-4d0e-9b8e-0c1f6a2e7d11")
LE = "Logical Elements"
BOM = b"\xef\xbb\xbf"
USERMETA = """<?xml version="1.0" encoding="utf-8"?>
<UserMetadataDoc xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
   <UserMetadata Id="%s" xmlns="">
      <dcec>
         <dc:identifier></dc:identifier>
         <dc:title></dc:title>
      </dcec>
      <revTable />
      <DescriptionCollection>
         <Description relativePath=".\\Description.html" format="HTML" />
         <Description relativePath=".\\Description.rtf" format="RTF" />
      </DescriptionCollection>
   </UserMetadata>
</UserMetadataDoc>"""
LOCRES = """<?xml version="1.0" encoding="utf-8"?>
<ResourcesDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">%s
  <Languages ID="0" Name="Default" />
</ResourcesDocument>"""


def gid(*parts):
    return str(uuid.uuid5(NS, "/".join(parts)))


def crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


DECL = re.compile(r"^(\s*)([A-Za-z_]\w*)\s*:\s*([^;{]+?)\s*(?:\{([^}]*)\})?\s*;(.*)$")


def tool_format(pou, variables, ports=None):
    """Declarations the way the tool writes them: every variable gets an Id and a group reference.
    Without the Id a flag like EHMI shows as ticked in the variable table but the HMI build does not see the variable.
    A variable flagged InputPort / OutputPort in a VAR block is a port: the tool keeps those in a VAR_GLOBAL block of
    the program's own sheet. They are collected into ports as (name, type, flags)."""
    group = gid(pou, "group")
    out = ["{ CustomGroupDefinition('%s', '') }" % group, ""]
    block, plain, port = None, [], []

    def flush():
        if plain:
            out.extend(["VAR"] + plain + ["END_VAR", ""])
        if port:
            out.extend(["VAR_GLOBAL"] + port + ["END_VAR", ""])
        del plain[:], port[:]

    for line in variables.replace("\r\n", "\n").split("\n"):
        word = line.strip()
        m = DECL.match(line)
        is_port = False
        if m and not line.lstrip().startswith("(*"):
            indent, name, typ, attrs, rest = m.groups()
            attrs = [a.strip() for a in (attrs or "").split(",") if a.strip()]
            is_port = block == "VAR" and ("InputPort" in attrs or "OutputPort" in attrs)
            if is_port and ports is not None:
                ports.append((name, " ".join(typ.split()), list(attrs)))
            attrs.append("CustomGroupReference('%s')" % group)
            line = "%s%s : %s { %s } {Id('%s')};%s" % (indent, name, " ".join(typ.split()), ", ".join(attrs), gid(pou, "var", name), rest)
        if block == "VAR":
            if word == "END_VAR":
                flush(); block = None
            else:
                (port if is_port else plain).append(line)
            continue
        if word == "VAR":
            block = "VAR"
            continue
        out.append(line)
    return "\n".join(out)


class Project:
    def __init__(self, base):
        z = zipfile.ZipFile(base)
        self.files = {i.filename: z.read(i.filename) for i in z.infolist() if not i.is_dir()}
        self.index = json.loads(self.files["PROJECT.proj"].decode("utf-8-sig"))
        self.content = self.index["Content"]
        self.le_id = next(c["Id"] for c in self.content if c["Name"] == LE and "ParentId" not in c)
        self.esmc_path = next(p for p in self.files if p.endswith("EsmConfiguration.esmc"))
        self.ports = {}                                  # POU -> [(name, type, flags)] of its port variables

    def attr(self, name, value):
        for a in self.index["Attributes"]:
            if a["Name"] == name:
                a["Value"] = value

    def remove_pou(self, name):
        folder = next((c for c in self.content if c["Name"] == name + ".pou"), None)
        if not folder:
            return
        self.content[:] = [c for c in self.content if c["Id"] != folder["Id"] and c.get("ParentId") != folder["Id"]]
        prefix = "PROJECT/Content/%s/%s.pou/" % (LE, name)
        for p in [p for p in self.files if p.startswith(prefix)]:
            del self.files[p]

    def add_pou(self, name, kind, variables, code, index, lang="st"):
        fid = gid(name)
        var_id = gid(name, "Variables.var")
        self.content.append({"Id": fid, "Name": name + ".pou", "Type": "Folder", "ParentId": self.le_id, "Area": "",
                             "Attributes": [{"Name": "FolderType", "Value": "PouFolder"}, {"Name": "Kind", "Value": kind},
                                            {"Name": "Usings", "Value": ""}, {"Name": "ContentType", "Value": kind},
                                            {"Name": "ParentIndex", "Value": str(index)}]})
        meta = ('<?xml version="1.0" encoding="utf-8"?>\n<Metadata>\n   <FolderType>PouFolder</FolderType>\n'
                '   <ContentType>%s</ContentType>\n   <Kind>%s</Kind>\n   <Usings></Usings>\n   <Id>%s</Id>\n'
                '   <ItemGroup>\n      <VariableWorksheet>\n         <Id>%s</Id>\n      </VariableWorksheet>\n'
                '   </ItemGroup>\n</Metadata>') % (kind, kind, fid, var_id)
        self.ports[name] = []
        items = [
            ("Metadata.meta", "MetadataDocument", [("Extension", ".meta")], crlf(meta).encode()),
            ("Variables.var", "VariableWorksheet", [("Extension", ".var")],
             BOM + crlf(tool_format(name, variables, self.ports[name])).encode()),
            ("Code." + lang, "CodeWorksheet", [("Extension", "." + lang), ("Type", "." + lang)], BOM + crlf(code).encode()),
            ("VersionHistory.usermeta", "UserMetadata", [("Extension", ".usermeta")], crlf(USERMETA % gid(name, "um")).encode()),
            ("Description.html", "UserMetadataDescription", [("Extension", ".html")], b""),
            ("Description.rtf", "UserMetadataDescription", [("Extension", ".rtf")], b""),
            ("Resources.locreslst", "LocalResourcesListDocument", [("DisplayName", "Resources"), ("Visible", "False")], b""),
            ("Variables.var.locres", "LocalResources", [("DisplayName", "Resources"), ("Visible", "False")], crlf(LOCRES % "").encode()),
            ("User.locres", "LocalResources", [("DisplayName", "Resources"), ("Visible", "False")],
             crlf(LOCRES % "\n  <IsUser>true</IsUser>").encode()),
        ]
        for fname, typ, attrs, data in items:
            stream = "%s/%s.pou/%s" % (LE, name, fname)
            self.content.append({"Id": var_id if fname == "Variables.var" else gid(name, fname), "Name": fname, "Type": typ,
                                 "Stream": stream, "ParentId": fid, "Area": "",
                                 "Attributes": [{"Name": n, "Value": v} for n, v in attrs]})
            self.files["PROJECT/Content/" + stream] = data

    def add_ports(self, tasks, io):
        """Ports of the programs (variables flagged InputPort / OutputPort) for every instance: an entry in the
        resource's global variables and one in the data list. io = {"M.CTRL": "Control Word"} puts the port into
        the same entry as that process data item of an I/O module, which is how the tool stores a connection."""
        gv_path = next(p for p in self.files if p.endswith("GlobalVariables.var"))
        dl_path = next(p for p in self.files if p.endswith("DataList.dl"))
        gv = self.files[gv_path].decode("utf-8-sig").replace("\r\n", "\n")
        dl = self.files[dl_path].decode("utf-8-sig").replace("\r\n", "\n")
        group = re.search(r"CustomGroupDefinition\('([^']+)', 'Default'\)", gv).group(1)
        plc = re.search(r'PlcIdentifier="([^"]+)"', dl).group(1)
        config, used = [], set()
        for t in tasks:
            for i in t["instances"]:
                for name, typ, flags in self.ports.get(i["program"], []):
                    full = "%s.%s" % (i["name"], name)
                    pid = gid("port", full)
                    config.append("    %s : %s { %s, CustomGroupReference('%s'), ProgramGlobal } {Id('%s')};"
                                  % (full, typ, ", ".join(flags), group, pid))
                    role = ('      <Role TypeName="%s" ObjectId="%s" SourceId="%s.L7_2">\n        <ComponentInstance>Arp.Plc.Eclr'
                            '</ComponentInstance>\n        <DataType>%s</DataType>\n        <Index />\n        <IsHmi>%s</IsHmi>\n'
                            '        <IsOpc>%s</IsOpc>\n        <IsProficloud>%s</IsProficloud>\n        <IsRedundant>False'
                            '</IsRedundant>\n        <IsRetain>False</IsRetain>\n        <Name>%s</Name>\n        <PortDataType>%s'
                            '</PortDataType>\n        <PortDataTypeDomain>Iec</PortDataTypeDomain>\n        <PortMultiplicity>1'
                            '</PortMultiplicity>\n        <Program>Arp.Plc.Eclr / %s</Program>\n        <ProgramInstance>%s'
                            '</ProgramInstance>\n      </Role>\n'
                            % ("InPort" if "InputPort" in flags else "OutPort", pid, plc, typ, "EHMI" in flags, "OPC" in flags,
                               "PROFICLOUD" in flags, name, typ, i["name"], i["name"]))
                    if full in io:
                        k = dl.find("<Name>%s</Name>" % io[full])
                        if k < 0:
                            raise ValueError("io: no process data item named %r in the base project" % io[full])
                        k = dl.index("</Role>\n", k) + len("</Role>\n")
                        dl = dl[:k] + role + dl[k:]
                        used.add(full)
                    else:
                        k = dl.rindex("  </DataList>")
                        dl = dl[:k] + '    <Datum Uuid="%s">\n      <FunctionText />\n%s    </Datum>\n' % (gid("datum", full), role) + dl[k:]
        missing = set(io) - used
        if missing:
            raise ValueError("io: no such port: %s" % ", ".join(sorted(missing)))
        if config:
            k = gv.index("\nVAR_GLOBAL")
            gv = gv[:k] + "\nVAR_CONFIG\n" + "\n".join(config) + "\nEND_VAR\n" + gv[k:]
        self.files[gv_path] = BOM + crlf(gv).encode()
        self.files[dl_path] = BOM + crlf(dl).encode()

    def set_tasks(self, tasks):
        """Replace the tasks of ESM1. Keeps the ESM definitions of the base project."""
        text = self.files[self.esmc_path].decode("utf-8-sig").replace("<Tasks />", "<Tasks>\n\t</Tasks>")   # as the tool saves an empty list
        head, rest = text.split("<Tasks>", 1)
        tail = rest.split("</Tasks>", 1)[1]
        esm1 = head.split('<Esm id="', 1)[1].split('"', 1)[0]
        out = ["<Tasks>"]
        for t in tasks:
            ns = int(t["interval_ms"] * 1_000_000)
            out.append('\t\t<Task id="%s" name="%s" taskType="CyclicTask" priority="%d" intervalTime="%d" watchdogTime="%d" '
                       'executionTimeThreshold="0" coreAffinity="0" stackSize="0" taskBuffer="None" comment="" esmId="%s" readonly="False">'
                       % (gid("task", t["name"]), t["name"], t.get("priority", 0), ns, ns, esm1))
            out.append("\t\t\t<ProgramInstances>")
            for i in t["instances"]:
                out.append('\t\t\t\t<ProgramInstance id="%s" name="%s" programType="%s" componentId="00000000-0000-0000-0000-000000000000" '
                           'libraryName="Arp.Plc.Eclr" componentName="Arp.Plc.Eclr" componentType="EclrComponent" comment="" readonly="False" groupName="" />'
                           % (gid("inst", i["name"]), i["name"], i["program"]))
            out.append("\t\t\t</ProgramInstances>")
            out.append("\t\t</Task>")
        out.append("\t</Tasks>")
        self.files[self.esmc_path] = BOM + (head + "\r\n".join(out) + tail).encode()
        # the same tasks and instances, as IEC text, in the resource settings (same ids)
        rs_path = next(p for p in self.files if p.endswith("ResourceSettings.set"))
        raw = self.files[rs_path]
        bom = BOM if raw.startswith(BOM) else b""
        rs = raw.decode("utf-8-sig").replace("\r\n", "\n")
        start = rs.index("\nTASK ") if "\nTASK " in rs else rs.index("\nEND_RESOURCE")
        lines = []
        for t in tasks:
            ms = "T#%gms" % t["interval_ms"]
            lines.append("TASK %s (INTERVAL := %s, PRIORITY := %d) { Watchdog(%s), Id('%s') };"
                         % (t["name"], ms, t.get("priority", 0), ms, gid("task", t["name"])))
        lines.append("")
        for t in tasks:
            for i in t["instances"]:
                lines.append("PROGRAM %s WITH %s : %s { Id('%s') };" % (i["name"], t["name"], i["program"], gid("inst", i["name"])))
        rs = rs[:start] + "\n" + "\n".join(lines) + "\n\nEND_RESOURCE\n"
        self.files[rs_path] = bom + crlf(rs).encode()

    def add_hmi_page(self, page, start=False):
        """Add an eHMI page (pxhmi.Page) under HMI Web Server > Application and put it in the navigation."""
        app = next(c for c in self.content if c["Name"] == "Application"
                   and any(a["Value"] == "HmiApplication" for a in c.get("Attributes", [])))
        nav = next(c for c in self.content if c["Name"] == "Navigation.hminav" and c.get("ParentId") == app["Id"])
        base = nav["Stream"].rsplit("/", 1)[0]
        pid = gid("hmipage", page.name)
        n = sum(1 for c in self.content if c.get("ParentId") == app["Id"])
        attrs = [("DisplayName", page.name)] + ([("StartPage", "True")] if start else []) + [("FolderType", "HmiPage"), ("ParentIndex", str(n))]
        self.content.append({"Id": pid, "Name": page.name + ".hmi", "Type": "Folder", "ParentId": app["Id"], "Area": "",
                             "Attributes": [{"Name": k, "Value": v} for k, v in attrs]})
        items = [
            ("Definition.hmipagedef", "HmiPageDefinition", [("HmiPageId", pid), ("ParentIndex", "0")], page.xml(pid)),
            ("Variables.hmivar", "HmiVariables", [("Visible", "False"), ("ParentIndex", "1")],
             '<?xml version="1.0" encoding="utf-8"?>\n<HmiVariables />'),
            ("Parameters.hmiparams", "HmiParameters", [("DisplayName", "Parameters"), ("HmiPageId", pid), ("Extension", ".hmiparams"), ("ParentIndex", "2")],
             '<?xml version="1.0" encoding="utf-8"?>\n<HmiParametersDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" />'),
            ("Definition.hmipagedef.locres", "LocalResources", [("Visible", "False"), ("DisplayName", "Resources"), ("ParentIndex", "3")], page.locres()),
        ]
        for fname, typ, at, data in items:
            stream = "%s/%s.hmi/%s" % (base, page.name, fname)
            self.content.append({"Id": gid("hmipage", page.name, fname), "Name": fname, "Type": typ, "Stream": stream,
                                 "ParentId": pid, "Area": "", "Attributes": [{"Name": k, "Value": v} for k, v in at]})
            self.files["PROJECT/Content/" + stream] = crlf(data).encode("utf-8")
        self.hmi_pages = getattr(self, "hmi_pages", []) + [pid]
        nodes = "".join('\n  <DocumentNode d3p1:type="DocumentPageReference" Id="%s" xmlns:d3p1="http://www.w3.org/2001/XMLSchema-instance" />' % i
                        for i in self.hmi_pages)
        self.files["PROJECT/Content/" + nav["Stream"]] = crlf(
            '<?xml version="1.0" encoding="utf-8"?>\n<NavigationDocument>\n <Nodes>%s\n </Nodes>\n</NavigationDocument>' % nodes).encode("utf-8")

    def set_hmi_server(self, login=None, rest=None):
        """HMI Web Server settings, stored in the device settings (.ds): login = False for no user check on the
        operator pages (bench use), rest = True to enable the REST data interface."""
        ds = next(p for p in self.files if p.endswith(".ds") and b"HMI:AccessRights" in self.files[p])   # the controller's, not a module's
        t = self.files[ds].decode("utf-8-sig")
        if login is not None:
            t = re.sub(r"(type='HMI:AccessRights'\]\" Type=\"Ade\.Fdcml\.Core\.Unsigned8\">)\d+", r"\g<1>%d" % (2 if login else 0), t)
        if rest is not None:
            t = re.sub(r"(type='HMI:EnableRestIF'\]\" Type=\"Ade\.Fdcml\.Core\.Boolean\">)\w+", r"\g<1>%s" % ("True" if rest else "False"), t)
        self.files[ds] = (BOM if self.files[ds].startswith(BOM) else b"") + t.encode("utf-8")

    def set_modbus_tcp(self, spec):
        """Registers of the remote Modbus TCP server that the base project holds under its Modbus TCP Client
        (made once in the tool). spec = {"ip": "192.168.1.50", "unit": 1, "port": 502, "registers":
        [{"name": "TEMP_HI", "fc": 4, "address": 0}, ...]}. Every register is one WORD, read each cycle of the
        client; its process data item is named <name>_input, which is what "io" links a program port to."""
        reg_path = next((p for p in self.files if p.endswith(".mbreg") and "/RecycleBin/" not in p), None)
        if not reg_path:
            raise ValueError("modbus_tcp: the base project has no Modbus TCP server (see reference/modbus-tcp.md)")
        ds_path = reg_path[:-len(".mbreg")] + ".ds"
        server = os.path.basename(reg_path)[:-len(".mbreg")]
        dl_path = next(p for p in self.files if p.endswith("DataList.dl"))
        dl = self.files[dl_path].decode("utf-8-sig").replace("\r\n", "\n")
        old = json.loads(self.files[reg_path].decode("utf-8-sig") or '{"Registers": []}')
        for r in old.get("Registers", []):               # registers the base came with: out of the data list
            for d in r["DataItems"]:
                dl = re.sub(r'    <Datum Uuid="[^"]+">\n(?:(?!</Datum>).)*?ObjectId="%s".*?</Datum>\n' % d["Id"], "", dl, flags=re.S)
        unit, regs, datums = int(spec.get("unit", 1)), [], ""
        for n, r in enumerate(spec["registers"]):
            if r["fc"] not in (3, 4):
                raise ValueError("modbus_tcp: only function 3 and 4 (read registers) are built, not %r" % r["fc"])
            item = gid("mbitem", r["name"])
            regs.append({"Id": gid("mbreg", r["name"]), "FunctionCode": r["fc"], "Name": r["name"], "DataType": "Word", "UnitId": unit,
                         "DataItems": [{"Id": item, "DataDirection": "Input", "Name": "input", "Address": r["address"], "Number": 1}]})
            label, off = r["name"] + "_input", "%d.0" % (2 * n)
            datums += ('    <Datum Uuid="%s">\n      <FunctionText />\n      <Role TypeName="ProcessDatum" ObjectIndex="%d" ObjectId="%s" SourceId="%s">\n'
                       '        <Access>Read</Access>\n        <ComponentIndex>-1</ComponentIndex>\n        <DataType>Bitstring16</DataType>\n'
                       '        <Handling>3</Handling>\n        <InputFrameId>0</InputFrameId>\n        <IsSafe>False</IsSafe>\n'
                       '        <Label>%s</Label>\n        <NodeId>1</NodeId>\n        <Offset>%s</Offset>\n        <OutputFrameId>0</OutputFrameId>\n'
                       '      </Role>\n    </Datum>\n' % (gid("mbpd", r["name"]), n, item, server, label, off))
            datums += ('    <Datum Uuid="%s">\n      <FunctionText />\n      <Role TypeName="OutPort" ObjectId="%s" SourceId="%s">\n'
                       '        <ComponentIndex>-1</ComponentIndex>\n        <ComponentInstance>Arp.Io.MbC</ComponentInstance>\n'
                       '        <DataType>Bitstring16</DataType>\n        <Index>%s</Index>\n        <IsHmi>False</IsHmi>\n        <IsOpc>False</IsOpc>\n'
                       '        <IsProficloud>False</IsProficloud>\n        <IsRedundant>False</IsRedundant>\n        <IsRetain>False</IsRetain>\n'
                       '        <Name>%s</Name>\n        <NodeId>1</NodeId>\n        <Offset>%s</Offset>\n        <PortDataType>Bitstring16</PortDataType>\n'
                       '        <PortDataTypeDomain>Fdcml</PortDataTypeDomain>\n        <PortMultiplicity>1</PortMultiplicity>\n'
                       '        <Program>Arp.Io.MbC</Program>\n      </Role>\n    </Datum>\n' % (gid("mbport", r["name"]), item, server, off, label, off))
        k = dl.find("    <RoleGroupList")
        k = k if k >= 0 else dl.rindex("  </DataList>")
        self.files[dl_path] = BOM + crlf(dl[:k] + datums + dl[k:]).encode()
        self.files[reg_path] = json.dumps({"Registers": regs}, separators=(",", ":")).encode()
        t = self.files[ds_path].decode("utf-8-sig")
        for typ, val in (("ModbusTCP:UnitID", unit), ("ModbusTCP:PortNo", spec.get("port", 502)), ("IP:IpAddress", spec["ip"])):
            t, c = re.subn(r"(type='%s'\]\" Type=\"[^\"]+\">)[^<]*" % typ, r"\g<1>%s" % val, t)
            if c != 1:
                raise ValueError("modbus_tcp: setting %s not found in the server's settings" % typ)
        self.files[ds_path] = (BOM if self.files[ds_path].startswith(BOM) else b"") + t.encode("utf-8")

    def set_opcua(self, visibility):
        """Which variables the controller's OPC UA server shows: "marked" (those flagged { OPC }), "all" or "none".
        The base projects come with "none", so the flag alone shows nothing."""
        val = {"none": "None", "marked": "Flagged", "all": "All"}[visibility]
        ds = next(p for p in self.files if p.endswith(".ds") and b"opcuaGdsPortsToProvideType" in self.files[p])
        t, c = re.subn(r"(OpcUAConfigurationDocument\.GdsPortsToProvide\.)\w+", r"\g<1>" + val, self.files[ds].decode("utf-8-sig"))
        if c != 1:
            raise ValueError("opcua: visibility setting not found in the base project")
        self.files[ds] = (BOM if self.files[ds].startswith(BOM) else b"") + t.encode("utf-8")

    def set_opcua_client(self, spec):
        """Connections of the firmware's OPC UA client to other servers and the variables it copies:
        {"connections": [{"name": "PLC_A", "url": "opc.tcp://192.168.1.10:4840", "user": "x", "password_env": "NAME"}],
         "groups": [{"type": "Subscribe", "cycle_ms": 500, "server": "PLC_A", "map": {"M.A_TEMP": "M.TEMP"}},
                    {"type": "Write", "cycle_ms": 500, "server": "PLC_A", "map": {"M.OUT1": "M.REMOTE1"}}],
         "trust_all": true}
        map = local program variable: variable on the server (both <instance>.<NAME>; the remote one must be visible
        there). Subscribe copies server -> local, Write local -> server. Password, one of: "password_env" = name of an
        environment variable read when the project is built (the password then stands in the project file in
        clear); "password_secret" = name of an entry in the secret store: the connections are then left out of the
        project and plc-opcua-client.sh puts them on the controller, the password never touching a file here."""
        path = next(p for p in self.files if p.endswith(".opcuaclicon"))
        if any(c.get("password_secret") for c in spec["connections"]):
            # the connections go to the controller by plc-opcua-client.sh, with the password from the secret store:
            # nothing of them in the project file, or the client would log in twice
            sys.stderr.write("opcua_client: connections are not in the project; run plc-opcua-client.sh <program dir> after the write\n")
            spec = dict(spec, connections=[], groups=[])
        ns = "http://phoenixcontact.com/OpcUA/PLCnext/GlobalDataSpace/"
        x = ['<?xml version="1.0" encoding="utf-8"?>', '<ClientConnectionsConfiguration xmlns="%s">' % ns]
        for g in spec.get("groups", []):
            x.append('  <VariableGroup GroupType="%s" CycleTime="%d">' % (g["type"], g.get("cycle_ms", 500)))
            for local, remote in g["map"].items():
                x += ['    <VariableMapping>', '      <LocalVariable Identifier="Arp.Plc.Eclr/%s" />' % local,
                      '      <RemoteVariable Identifier="s=Arp.Plc.Eclr/%s" ShortName="" Namespace="%s" ServerName="%s" />' % (remote, ns, g["server"]),
                      '    </VariableMapping>']
            x.append('  </VariableGroup>')
        for n, c in enumerate(spec["connections"], start=1):
            pw = os.environ.get(c["password_env"], "") if c.get("password_env") else ""
            if c.get("password_env") and not pw:
                sys.stderr.write("opcua_client: %s is not set, connection %s gets no password\n" % (c["password_env"], c["name"]))
            esc = lambda v: v.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
            x.append('  <Connection Name="%s" ServerUrl="%s" SecurityMode="%s" SecurityPolicy="%s" UserName="%s" Password="%s" ServerIndex="%d" />'
                     % (c["name"], c["url"], c.get("security_mode", "SignAndEncrypt"), c.get("security_policy", "BestAvailable"),
                        esc(c.get("user", "")), esc(pw), n))
        x.append('</ClientConnectionsConfiguration>')
        self.files[path] = BOM + crlf("\n".join(x)).encode("utf-8") if spec["connections"] else b""
        if spec.get("trust_all"):                        # bench: take the server's certificate without a trust store entry
            ds = next(p for p in self.files if p.endswith(".ds") and b"opcuaClientModuleApplicationAuthentication" in self.files[p])
            t = self.files[ds].decode("utf-8-sig")
            for name, val in (("SessionSecurityDefinitionEnabled", "True"), ("ApplicationAuthentication", "False"),
                              ("ApplicationUriCheck", "False"), ("CertificateHostnameCheck", "False")):
                t = re.sub(r"(Para\[@uID='opcuaClientModule%s'\]/Current\" Type=\"Ade\.Fdcml\.Core\.Boolean\">)\w+" % name, r"\g<1>" + val, t)
            self.files[ds] = (BOM if self.files[ds].startswith(BOM) else b"") + t.encode("utf-8")

    def add_library(self, name):
        """Reference a library that ships with the tool, e.g. 'Symbols-Schematic'."""
        path = "%SYSTEMLIBRARIES%/" + name + ".plcnlx2"
        if not any(r["Path"] == path for r in self.index["References"]):
            self.index["References"].append({"Path": path, "IsReadOnly": True})

    def set_target(self, target):
        """Where the Cockpit connects: {"simulation": true} or {"ip": "192.168.1.10"}. Two lines of the resource settings."""
        rs_path = next(p for p in self.files if p.endswith("ResourceSettings.set"))
        rs = self.files[rs_path].decode("utf-8")
        if target.get("simulation"):
            meta, ip = "UniqueId=TcpIp_Simulation;IsBackup=", "0.0.0.0"
        else:
            meta, ip = "UniqueId=TCP/IP;IsBackup=False", target["ip"]
        rs = re.sub(r"CommunicationMetadata := '[^']*'", "CommunicationMetadata := '%s'" % meta, rs)
        rs = re.sub(r"-ip[0-9.]+ ", "-ip%s " % ip, rs)
        if "timeout_ms" in target:                       # a slow target (emulated simulation) needs more than the 2 s
            rs = re.sub(r"-to[0-9]+", "-to%d" % target["timeout_ms"], rs)
        self.files[rs_path] = rs.encode("utf-8")
        if not target.get("simulation"):                 # the controller's own address in its settings: the same one
            ds = next(p for p in self.files if p.endswith(".ds") and b"HMI:AccessRights" in self.files[p])
            t = self.files[ds].decode("utf-8-sig")
            t = re.sub(r"(Layer3-4\[@uID='L34_1'\]/InstanceObjList/Obj\[@uID='ip100' type='IP:IpAddress'\]\" Type=\"Ade\.Fdcml\.Core\.Ipv4\">)[0-9.]*",
                       r"\g<1>%s" % ip, t)
            self.files[ds] = (BOM if self.files[ds].startswith(BOM) else b"") + t.encode("utf-8")

    def save(self, path):
        self.files["PROJECT.proj"] = crlf(json.dumps(self.index, indent=2)).encode()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name in sorted(self.files):
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))     # fixed time: same input, same file
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, self.files[name])
        with open(path, "wb") as f:
            f.write(buf.getvalue())


HOME = os.environ.get("PXE_HOME", os.path.expanduser("~/.plcnext-engineer"))


def find_base(pdir, base):
    """A base project is an empty project the tool made for one controller type and firmware (pxe.sh setup).
    'base' is a file path relative to the program dir, or a name looked up in <work folder>/base/<name>.plcnx2."""
    for cand in (os.path.join(pdir, base), os.path.join(HOME, "base", base), os.path.join(HOME, "base", base + ".plcnx2")):
        if os.path.isfile(cand):
            return cand
    have = sorted(f[:-8] for f in os.listdir(os.path.join(HOME, "base")) if f.endswith(".plcnx2")) if os.path.isdir(os.path.join(HOME, "base")) else []
    sys.exit("base project %r not found. Bases in %s/base: %s" % (base, HOME, ", ".join(have) or "none (run pxe.sh setup)"))


def strip(src, dst):
    """Make a clean base from a project the tool saved: drop every POU and HMI page, keep the hardware."""
    p = Project(src)
    for c in [c for c in p.content if c["Name"].endswith(".pou")]:
        p.remove_pou(c["Name"][:-4])
    pages = [c for c in p.content if c["Name"].endswith(".hmi") and c["Type"] == "Folder"]
    for pg in pages:
        p.content[:] = [c for c in p.content if c["Id"] != pg["Id"] and c.get("ParentId") != pg["Id"]]
        for f in [f for f in p.files if "/%s/" % pg["Name"] in f]:
            del p.files[f]
    for f in [f for f in p.files if f.endswith("Navigation.hminav")]:
        p.files[f] = b'<?xml version="1.0" encoding="utf-8"?><NavigationDocument />'
    p.set_tasks([])
    p.save(dst)
    return len(p.files)


def build(pdir, out=None):
    spec = json.load(open(os.path.join(pdir, "program.json")))
    p = Project(find_base(pdir, spec["base"]))
    p.attr("Title", spec["name"])
    p.attr("Identifier", gid("project", spec["name"]))
    p.remove_pou("Main")
    for n, pou in enumerate(spec["pous"], start=1):
        p.remove_pou(pou["name"])                        # the base may be an earlier build of this program
        src = os.path.join(pdir, "src", pou["name"])
        var = open(os.path.join(src, "Variables.var")).read()
        if os.path.exists(os.path.join(src, "Code.ld.py")):          # ladder / function block diagram (pxld.py)
            import importlib.util, pxld
            m = importlib.util.spec_from_file_location("code_" + pou["name"], os.path.join(src, "Code.ld.py"))
            mod = importlib.util.module_from_spec(m); m.loader.exec_module(mod)
            d = pxld.LD({q["name"]: pxld.pins_from_var(open(os.path.join(pdir, "src", q["name"], "Variables.var")).read())
                         for q in spec["pous"] if q["kind"] == "FunctionBlock"})
            mod.code(d)
            p.add_pou(pou["name"], pou["kind"], var, d.xml(), n, lang="ld")
        else:
            p.add_pou(pou["name"], pou["kind"], var, open(os.path.join(src, "Code.st")).read(), n)
    p.set_tasks(spec["tasks"])
    if "modbus_tcp" in spec:                             # registers of the remote server in the base project
        p.set_modbus_tcp(spec["modbus_tcp"])
    if any(p.ports.values()):                        # program variables flagged InputPort / OutputPort
        p.add_ports(spec["tasks"], spec.get("io", {}))
    if "target" in spec:
        p.set_target(spec["target"])
    if "hmi_server" in spec:                             # {"login": false, "rest": true}
        p.set_hmi_server(**spec["hmi_server"])
    if "opcua" in spec:                                  # {"visibility": "marked"}
        p.set_opcua(spec["opcua"].get("visibility", "marked"))
    if "opcua_client" in spec:
        p.set_opcua_client(spec["opcua_client"])
    for lib in spec.get("libraries", []):
        p.add_library(lib)
    if "hmi" in spec:                                    # a Python file in the program dir with pages() -> [pxhmi.Page]
        import importlib.util
        m = importlib.util.spec_from_file_location("hmi_pages", os.path.join(pdir, spec["hmi"]))
        mod = importlib.util.module_from_spec(m); m.loader.exec_module(mod)
        for i, page in enumerate(mod.pages()):
            p.add_hmi_page(page, start=(i == 0))
            if i == 0:
                os.makedirs(HOME, exist_ok=True)
                open(os.path.join(HOME, "page-size"), "w", newline="\n").write("%g %g\n" % (page.width, page.height))
    out = out or os.path.join(pdir, spec["name"] + ".plcnx2")
    p.save(out)
    return out, len(spec["pous"])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--strip":                         # pxproj.py --strip <saved project> <base out>
        print("%s: %d files" % (sys.argv[3], strip(sys.argv[2], sys.argv[3])))
        sys.exit(0)
    out, n = build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print("%s: %d POUs, %d bytes" % (out, n, os.path.getsize(out)))
