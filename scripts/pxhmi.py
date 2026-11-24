#!/usr/bin/env python3
"""pxhmi.py - PLCnext Engineer eHMI pages as XML (Definition.hmipagedef), written without the tool.

    page = Page("Home", 1280, 720)
    page.text("t1", 40, 20, 400, 30, "Hot water")
    page.value("v1", 40, 60, 120, 30, "DH.TE1")                       # text that shows an expression
    page.rect("r1", 40, 100, 30, 30, fill="#FF8ACCD1", visible="DH.P1_RUN")
    project.add_hmi_page(page, start=True)                            # pxproj.Project

Object attributes are copied from pages the tool wrote itself (template HmiUserManagementAXCF2152, Engineer 2026.6).
"""
import re
from xml.sax.saxutils import escape, quoteattr

# symbols of the library "Symbols-Schematic" (Engineer 2026.6): name -> id of the parameter that takes a BOOL variable
SCHEMATIC = {"Pump": "ae8baa5a-a5c3-47d4-b983-352180bfd9f9",            # Running
             "Valve": "43b566cb-4a95-4c0a-9d33-22770404d009",           # Open
             "Control Valve": "14bfddd8-83e8-4e1d-805b-2fe74963d8e0"}   # Open


SIZE = {"Pump": (20.5, 20.5), "Control Valve": (45, 55), "Valve": (45, 30)}     # about, at scale 1 (measured on screen)


def hid(oid):
    """Object id as written into the page. The tool rejects some plain ids (seen: a page with ids like 'on', 'sum',
    'at' failed with "The ID of the HMI object is invalid"); with a fixed prefix every id is accepted."""
    return "obj_" + re.sub(r"[^A-Za-z0-9_]", "_", str(oid))


def varref(tag, variable):
    """<tag><Name>instance</Name><Suffix>.variable</Suffix></tag> for 'instance.variable'."""
    inst, _, rest = variable.partition(".")
    return "<%s><Name>%s</Name>%s</%s>" % (tag, inst, "<Suffix>.%s</Suffix>" % rest if rest else "", tag)

SCOPES = """<EnableSecurityScope>Always</EnableSecurityScope>
<EnableSecurityScopeOperator>Equal</EnableSecurityScopeOperator>
<EnableSecurityScopeLevel>0</EnableSecurityScopeLevel>
<VisibleSecurityScope>Always</VisibleSecurityScope>
<VisibleSecurityScopeOperator>Equal</VisibleSecurityScopeOperator>
<VisibleSecurityScopeLevel>0</VisibleSecurityScopeLevel>"""
FONT = 'FontFamily="Arial" FontSize="%g" FontStyle="normal" FontWeight="%d" FontColor="%s"'


def expr(tag, text):
    return '<%s xsi:type="SimpleSTExpression"><ExpressionLine>%s</ExpressionLine></%s>' % (tag, escape(text), tag)


class Page:
    def __init__(self, name, width=1280, height=720, fill="#FFF6F6F6"):
        self.name, self.width, self.height, self.fill = name, width, height, fill
        self.objects, self.texts = [], {}

    def _obj(self, typ, oid, x, y, w, h, attrs, fill, dynamics="", extra="", tab="false", pivot=(0, 0)):
        """pivot: the point (relative to x, y) that rotation and scaling keep in place; Origin = Location + pivot."""
        px, py = pivot
        self.objects.append(
            '<HmiObject xsi:type="%s" Rotation="0" ID="%s" IsTabSelectable="%s" TabOrder="0" %s>\n'
            '<Origin><X>%g</X><Y>%g</Y></Origin>\n<Location><X>%g</X><Y>%g</Y></Location>\n'
            '<TransformCenter><X>%g</X><Y>%g</Y></TransformCenter>\n%s%s\n'
            '<Fill xsi:type="SolidFill" Color="%s" />\n<DashStyle><Offset>0</Offset><Dashes /></DashStyle>\n'
            '<Size><Width>%g</Width><Height>%g</Height></Size>\n%s</HmiObject>'
            % (typ, hid(oid), tab, attrs, x + px, y + py, x, y, px, py, dynamics, SCOPES, fill, w, h, extra))

    @staticmethod
    def _dyn(visible=None, text=None, fill=None, fmt=None):
        """fill = (expression, [(threshold, colour), ...]): colour of the highest threshold <= value."""
        d = ""
        if text:
            d += '<Dynamic xsi:type="TextDynamic" %sTargetProperty="Text">%s</Dynamic>\n' % (
                'Format="%s" ' % fmt if fmt else "", expr("Expression", text))
        if fill:
            rows = "".join('<FillDynamicThresholdData Blink="false"><Threshold xmlns:q%d="http://www.w3.org/2001/XMLSchema" '
                           'xsi:type="q%d:int">%d</Threshold><Value xsi:type="SolidFill" Color="%s" /></FillDynamicThresholdData>'
                           % (i, i, t, c) for i, (t, c) in enumerate(fill[1], start=1))
            d += ('<Dynamic xsi:type="FillDynamic" TargetProperty="Fill" Interpolate="false" Rate="None">%s'
                  '<ThresholdData>%s</ThresholdData></Dynamic>\n' % (expr("Expression", fill[0]), rows))
        if visible:
            # the tool's rule is "change (hide) when the expression is ..."; hide when FALSE = visible when TRUE
            d += '<Dynamic xsi:type="VisibilityDynamic" ChangeWhen="False">%s</Dynamic>\n' % expr("Expression", visible)
        return d

    def text(self, oid, x, y, w, h, text, size=16, color="#FF3E3D40", weight=400, align="Left", visible=None, value=None, fmt=None):
        self.texts[hid(oid) + ".Text"] = text
        attrs = ('LineColor="#FFCCD0D2" LineWidth="0" Text=%s %s HorizontalTextAlignment="%s" GuiStyle="Flat" '
                 'TextWrapping="WrapWithOverflow"' % (quoteattr(text), FONT % (size, weight, color), align))
        self._obj("HmiText", oid, x, y, w, h, attrs, "#00FFFFFF", self._dyn(visible, value, fmt=fmt))

    def value(self, oid, x, y, w, h, expression, fmt="fixed1", **kw):
        """A text whose content is an expression, e.g. a PLC variable. fmt "fixed1" = one decimal; without a format a
        REAL shows all its digits and is clipped (fmt=None only for texts and whole numbers)."""
        self.text(oid, x, y, w, h, "0", value=expression, fmt=fmt, **kw)

    def rect(self, oid, x, y, w, h, fill="#FFECEDED", line="#FFCCD0D2", line_width=1, visible=None, fill_by=None,
             radius=0, grow=None, axis="x"):
        """grow = (expression, low, high): width (axis "x", grows to the right) or height (axis "y", grows upwards)
        follows the value from 0 to full (a bar)."""
        attrs = 'LineColor="%s" LineWidth="%g" %s' % (line, line_width, FONT % (18, 400, "#FF3E3D40"))
        dyn = self._dyn(visible, fill=fill_by)
        if grow:
            sx, sy = (0, 1) if axis == "x" else (1, 0)
            dyn += ('<Dynamic xsi:type="ScaleDynamic" LowRange="%g" HighRange="%g">%s<StartScale><X>%d</X><Y>%d</Y></StartScale>'
                    '<EndScale><X>1</X><Y>1</Y></EndScale><MinPercentScale>0</MinPercentScale><MaxPercentScale>0</MaxPercentScale>'
                    '</Dynamic>\n' % (grow[1], grow[2], expr("Expression", grow[0]), sx, sy))
        self._obj("Rectangle", oid, x, y, w, h, attrs, fill, dyn,
                  "<CornerRadii><Width>%g</Width><Height>%g</Height></CornerRadii>\n" % (radius, radius),
                  pivot=(0, h) if grow and axis == "y" else (0, 0))

    def ellipse(self, oid, x, y, w, h, fill="#FFB8BCBF", line="#FF8A8F93", line_width=1, visible=None, fill_by=None):
        attrs = ('LineColor="%s" LineWidth="%g" %s IsTextWrapping="false" TextDirection="LeftToRight" HorizontalTextAlignment="Left" '
                 'GuiStyle="Flat" TextMarginTop="0" TextMarginBottom="0" TextMarginLeft="0" TextMarginRight="0"'
                 % (line, line_width, FONT % (18, 400, "#FF3E3D40")))
        self._obj("Ellipse", oid, x, y, w, h, attrs, fill, self._dyn(visible, fill=fill_by))

    def line(self, oid, x1, y1, x2, y2, color="#FF3E3D40", width=1):
        self.objects.append(
            '<HmiObject xsi:type="Line" Rotation="0" ID="%s" IsTabSelectable="false" TabOrder="0" LineColor="%s" LineWidth="%g" %s '
            'IsTextWrapping="false" TextDirection="LeftToRight" HorizontalTextAlignment="Left" GuiStyle="Flat" TextMarginTop="0" '
            'TextMarginBottom="0" TextMarginLeft="0" TextMarginRight="0" EndCapType="Square" StartLineEndType="None" '
            'EndLineEndType="None" StartLineEndSize="Medium" EndLineEndSize="Medium" PathType="PolylinePath">\n'
            '<Origin><X>%g</X><Y>%g</Y></Origin>\n<Location><X>%g</X><Y>%g</Y></Location>\n'
            '<TransformCenter><X>0</X><Y>0</Y></TransformCenter>\n%s\n<Fill xsi:type="SolidFill" Color="#00FFFFFF" />\n'
            '<DashStyle><Offset>0</Offset><Dashes /></DashStyle>\n'
            '<SubPaths IsClosed="false"><Start><X>0</X><Y>0</Y></Start><Segments xsi:type="LinePathSegment"><End><X>%g</X><Y>%g</Y></End>'
            '</Segments></SubPaths>\n</HmiObject>'
            % (hid(oid), color, width, FONT % (18, 400, "#FF3E3D40"), x1, y1, x1, y1, SCOPES, x2 - x1, y2 - y1))

    def button(self, oid, x, y, w, h, text, write=None, step=None, size=14, page=None):
        """write = (variable, constant): set on click. step = (variable, amount): add on click. page = name of another
        page of the project: show it on click (Engineer's "Load page"; pxproj puts in the page's id)."""
        self.texts[hid(oid) + ".Text"] = text
        act = ""
        if page:
            act = '<Action xsi:type="LoadPageAction" Gesture="Click" ID="A1" Page="@page:%s@" />\n' % escape(page)
        if write:
            act = ('<Action xsi:type="WriteValueAction" Gesture="Click" ID="A1" SourceType="Constant" SourceConstant=%s>'
                   '%s</Action>\n' % (quoteattr(str(write[1])), varref("DestinationVariableInstance", write[0])))
        if step:
            act = ('<Action xsi:type="IncrementValueAction" Gesture="Click" ID="A1" StepConstant="%g">'
                   '%s</Action>\n' % (step[1], varref("VariableInstance", step[0])))
        attrs = ('NextId="2" LineColor="#FFCCD0D2" LineWidth="1" Text=%s %s IsTextWrapping="false" TextDirection="LeftToRight" '
                 'HorizontalTextAlignment="Center" GuiStyle="Flat" TextMarginTop="0" TextMarginBottom="0" TextMarginLeft="0" '
                 'TextMarginRight="0" EndCapType="Square" IsLatching="false" IsDefault="false" ImpulseTime="0" ImagePlacement="Left" '
                 'ImageAreaWidthUnits="Percent" ImageAreaHeightUnits="Percent" Margin="0" '
                 'ImageWhenDownId="00000000-0000-0000-0000-000000000000" ImageScaling="Fill"'
                 % (quoteattr(text), FONT % (size, 400, "#FF3E3D40")))
        extra = ('<FillWhenDown xsi:type="SolidFill" Color="#FF8ACCD1" />\n<ImageArea><Width>50</Width><Height>50</Height></ImageArea>\n'
                 '<CornerRadii><Width>0</Width><Height>0</Height></CornerRadii>\n')
        self._obj("Button", oid, x, y, w, h, attrs, "#FFECEDED", act, extra, tab="true")

    def chart(self, oid, x, y, w, h, session, pens, minutes=15, sampling_ms=1000, mode="Raw", left=(0, 0), right=(0, 0),
              zoom=False, line="#FFCCD0D2"):
        """Trend chart over a DataLogger session (pxproj set_datalogger / program.json "datalogger"); it shows only
        what the session has recorded. pens = [(variable, colour, "Left" | "Right"), ...], one per variable of the
        session, in the session's order (Engineer rebuilds the pens when they differ). left / right = (min, max) of
        the axis, (0, 0) = automatic; the right axis is shown when a pen uses it. Raw mode: every sample, at most
        1000 per pen, time range = samples x sampling interval; Downsample: at most 100 points over the range."""
        cap = 1000 if mode == "Raw" else 100
        samples = min(cap, int(minutes * 60000 / sampling_ms)) if mode == "Raw" else cap
        span = samples * sampling_ms / 1000.0 if mode == "Raw" else minutes * 60.0   # Engineer recomputes it so in Raw
        tr = "%03d:%02d:%06.3f" % (span // 3600, span % 3600 // 60, span % 60)
        paths = ["Arp.Plc.Eclr/" + p[0] for p in pens]
        trends = "".join('<Trend><VariablePath>%s</VariablePath><IsIncluded>true</IsIncluded><LineColor>#%s</LineColor>'
                         '<Placement>%s</Placement></Trend>' % (pa, c.lstrip("#")[-6:], side)
                         for pa, (_, c, side) in zip(paths, pens))           # colour as Engineer writes it: #RRGGBB
        axis = lambda tag, vis, r: "<%s><Visible>%s</Visible><MinValue>%g</MinValue><MaxValue>%g</MaxValue></%s>" % (tag, vis, r[0], r[1], tag)
        has_right = any(p[2] == "Right" for p in pens)
        self.objects.append(
            '<HmiObject xsi:type="HmiChart" Rotation="0" ID="%s" IsTabSelectable="false" TabOrder="0" LineColor="%s" LineWidth="1" %s '
            'IsTextWrapping="false" TextDirection="LeftToRight" HorizontalTextAlignment="Left" GuiStyle="Flat" TextMarginTop="0" '
            'TextMarginBottom="0" TextMarginLeft="0" TextMarginRight="0" EndCapType="Square">\n'
            '<Origin><X>%g</X><Y>%g</Y></Origin>\n<Location><X>%g</X><Y>%g</Y></Location>\n'
            '<TransformCenter><X>0</X><Y>0</Y></TransformCenter>\n%s\n<DashStyle><Offset>0</Offset><Dashes /></DashStyle>\n'
            '<Size><Width>%g</Width><Height>%g</Height></Size>\n<Trends>%s</Trends>\n'
            '<DataLoggerSessionRef><InstanceName>%s</InstanceName><Paths>%s</Paths></DataLoggerSessionRef>\n'
            '<MinimumInterval>%d</MinimumInterval>\n<DataMode>%s</DataMode>\n<TrendSampleSize>%d</TrendSampleSize>\n'
            '<AllAvailableOnTimeRange>false</AllAvailableOnTimeRange>\n<XScaleDisplayMode>MM:SS</XScaleDisplayMode>\n'
            '<PreloadData>false</PreloadData>\n<AllowZoom>%s</AllowZoom>\n%s\n%s\n'
            '<HorizontalAxis><MajorTickCount>0</MajorTickCount><MinorTickCount>0</MinorTickCount></HorizontalAxis>\n'
            '<TimeRange>%s</TimeRange>\n</HmiObject>'
            % (hid(oid), line, FONT % (18, 400, "#FF3E3D40"), x, y, x, y, SCOPES, w, h, trends, escape(session),
               "".join("<string>%s</string>" % pa for pa in paths), sampling_ms, mode, samples, str(zoom).lower(),
               axis("LeftAxis", "true", left), axis("RightAxis", str(has_right).lower(), right), tr))

    def poly(self, oid, points, fill="#FFFFFFFF", line="#FF2B2F33", line_width=2, fill_by=None, visible=None):
        """Closed shape through the points [(x, y), ...], filled."""
        x0, y0 = points[0]
        segs = "".join('<Segments xsi:type="LinePathSegment"><End><X>%g</X><Y>%g</Y></End></Segments>' % (x - x0, y - y0)
                       for x, y in points[1:])
        self.objects.append(
            '<HmiObject xsi:type="Line" Rotation="0" ID="%s" IsTabSelectable="false" TabOrder="0" LineColor="%s" LineWidth="%g" %s '
            'IsTextWrapping="false" TextDirection="LeftToRight" HorizontalTextAlignment="Left" GuiStyle="Flat" TextMarginTop="0" '
            'TextMarginBottom="0" TextMarginLeft="0" TextMarginRight="0" EndCapType="Square" StartLineEndType="None" '
            'EndLineEndType="None" StartLineEndSize="Medium" EndLineEndSize="Medium" PathType="PolylinePath">\n'
            '<Origin><X>%g</X><Y>%g</Y></Origin>\n<Location><X>%g</X><Y>%g</Y></Location>\n'
            '<TransformCenter><X>0</X><Y>0</Y></TransformCenter>\n%s%s\n<Fill xsi:type="SolidFill" Color="%s" />\n'
            '<DashStyle><Offset>0</Offset><Dashes /></DashStyle>\n'
            '<SubPaths IsClosed="true"><Start><X>0</X><Y>0</Y></Start>%s</SubPaths>\n</HmiObject>'
            % (hid(oid), line, line_width, FONT % (18, 400, "#FF3E3D40"), x0, y0, x0, y0, self._dyn(visible, fill=fill_by), SCOPES, fill, segs))

    def pump(self, oid, cx, cy, state, r=24, flow="right", colors=None):
        """Pump drawn on the point (cx, cy) - put that on the pipe's centre line. 'state' is an expression: a BOOL
        (running) or a number; colors = [(threshold, colour), ...], default red when 0 (stopped), green when 1
        (running), red from 2 on (fault). flow: "right" or "left", the way the arrow points."""
        colors = colors or [(0, "#FFD93A32"), (1, "#FF2EA043"), (2, "#FFD93A32")]
        self.ellipse(oid, cx - r, cy - r, 2 * r, 2 * r, fill=colors[0][1], line="#FF2B2F33", line_width=2, fill_by=(state, colors))
        k = 1 if flow == "right" else -1
        self.poly(str(oid) + "_arrow", [(cx - k * r * 0.42, cy - r * 0.62), (cx + k * r * 0.74, cy), (cx - k * r * 0.42, cy + r * 0.62)],
                  fill="#FFFFFFFF", line="#FF2B2F33", line_width=1.5)

    def valve(self, oid, cx, cy, position, size=20, colors=None):
        """Control valve drawn on the point (cx, cy) - put that on the pipe's centre line. 'position' is an expression,
        0..100 % (or a BOOL): the body is grey when closed, light green when open, full green from half open on."""
        colors = colors or [(0, "#FFB8BCBF"), (1, "#FF8FD3A5"), (50, "#FF2EA043")]
        s = size
        self.line(str(oid) + "_stem", cx, cy, cx, cy - s * 1.1, color="#FF2B2F33", width=2)
        self.rect(str(oid) + "_act", cx - s * 0.55, cy - s * 1.75, s * 1.1, s * 0.65, fill="#FFFFFFFF", line="#FF2B2F33", line_width=2, radius=4)
        self.poly(str(oid) + "_l", [(cx - s, cy - s * 0.62), (cx, cy), (cx - s, cy + s * 0.62)], fill=colors[0][1], fill_by=(position, colors))
        self.poly(str(oid) + "_r", [(cx + s, cy - s * 0.62), (cx, cy), (cx + s, cy + s * 0.62)], fill=colors[0][1], fill_by=(position, colors))

    def symbol(self, oid, x, y, name, variable, scale=1.0, rotation=0, size=None):
        """A library symbol (see SCHEMATIC) whose BOOL parameter is bound to a PLC variable. The project needs the library.
        rotation in degrees about the middle of the symbol; size = (w, h) of the symbol at scale 1 (default: SIZE[name])."""
        w, h = size or SIZE.get(name, (0, 0))
        self.objects.append(
            '<HmiObject xsi:type="SymbolInstance" Rotation="%g" ID="%s" IsTabSelectable="false" TabOrder="0">\n'
            '<Origin><X>%g</X><Y>%g</Y></Origin>\n<Location><X>%g</X><Y>%g</Y></Location>\n'
            '<TransformCenter><X>%g</X><Y>%g</Y></TransformCenter>\n%s\n<Scale><Height>%g</Height><Width>%g</Width></Scale>\n'
            '<SymbolName>%s</SymbolName>\n<Parameters><Parameter xsi:type="ParameterBindingVariable" ParameterID="%s">%s</Parameter></Parameters>\n'
            '</HmiObject>' % (rotation, hid(oid), x + w * scale / 2, y + h * scale / 2, x, y, w * scale / 2, h * scale / 2, SCOPES, scale, scale,
                              name, SCHEMATIC[name], varref("SourceInstance", variable)))     # Origin = pivot = Location + TransformCenter

    def xml(self, page_id):
        return ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<HmiPage xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" Name="%s" BorderWidth="0">\n'
                '<References><Documents><Document Id="%s" NodeType="HmiPage" Name="%s" /></Documents></References>\n'
                '<Layers><Layer><Objects>\n%s\n</Objects></Layer></Layers>\n'
                '<Size><Width>%g</Width><Height>%g</Height></Size>\n<MarginColorString>#FF000000</MarginColorString>\n'
                '<AvailableSecurityScope>Always</AvailableSecurityScope>\n'
                '<AvailableSecurityScopeOperator>Equal</AvailableSecurityScopeOperator>\n'
                '<AvailableSecurityScopeLevel>0</AvailableSecurityScopeLevel>\n'
                '<Fill xsi:type="SolidFill" Color="%s" />\n</HmiPage>'
                % (self.name, page_id, self.name, "\n".join(self.objects), self.width, self.height, self.fill))

    def locres(self):
        rows = "".join('\n  <Resources ID="%d" Name=%s>\n    <Values LanguageID="0" LocalValue=%s />\n  </Resources>'
                       % (100 + i, quoteattr(k), quoteattr(v)) for i, (k, v) in enumerate(self.texts.items()))
        return ('<?xml version="1.0" encoding="utf-8"?>\n<ResourcesDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
                '  <NextResourceID>%d</NextResourceID>\n  <Languages ID="0" Name="Default" />%s\n</ResourcesDocument>'
                % (100 + len(self.texts), rows))
