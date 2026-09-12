# SPDX-License-Identifier: GPL-3.0-only
"""Print an existing verified route; no routing, downloads or adapter imports."""
import argparse, json, re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter


def validate(d):
    if d.get('status') != 'ok' or d.get('verified_source') is not True:
        raise ValueError('An existing verified successful route is required')
    for k in ('start_label','end_label','distance_display','eta_display','snapshot','map_png'):
        if not isinstance(d.get(k),str) or not d[k].strip(): raise ValueError('Missing '+k)
    if not re.fullmatch(r'\d+(?:\.\d+)? mi',d['distance_display']): raise ValueError('Total must be miles')
    if not 1 <= len(d.get('maneuvers',[])) <= 300: raise ValueError('Missing or oversized maneuver list')
    for m in d['maneuvers']:
        if not m.get('instruction') or not re.fullmatch(r'\d+(?:\.\d+)? (?:mi|ft)',m.get('distance_display','')):
            raise ValueError('Each maneuver needs an instruction and preserved feet/miles distance')
        if not isinstance(m.get('road'),str): raise ValueError('Road must be supplied (empty means unknown)')
    if not Path(d['map_png']).is_file(): raise ValueError('Existing map PNG required')


def render(d, output):
    validate(d)
    title=d['start_label']+' to '+d['end_label']
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RouteTitle',fontName='Helvetica-Bold',fontSize=20,leading=24,spaceAfter=12))
    styles.add(ParagraphStyle(name='RouteBody',fontName='Helvetica',fontSize=11,leading=15,spaceAfter=6))
    styles.add(ParagraphStyle(name='SmallRoute',fontName='Helvetica',fontSize=9,leading=12,spaceAfter=5))
    p=lambda s,style='RouteBody':Paragraph(s,styles[style])
    esc=lambda s:escape(str(s))
    story=[p(esc(title),'RouteTitle'),p('<b>'+esc(d['distance_display'])+' | Estimated driving time: '+esc(d['eta_display'])+'</b>'),p('Map snapshot: '+esc(d['snapshot'])+'. Estimate from saved offline route; no live traffic or assurance roads are open.'),p('<b>START:</b> '+esc(d['start_label'])+'<br/><b>END:</b> '+esc(d['end_label'])),p(esc(d.get('full_input','')),'SmallRoute'),p(esc(d.get('endpoint_scope','Town centers snapped to car roads, not exact street addresses.')),'SmallRoute')]
    im=Image(d['map_png']); iw,ih=im.imageWidth,im.imageHeight; im.drawWidth=504; im.drawHeight=504*ih/iw
    if im.drawHeight>460: im.drawWidth*=460/im.drawHeight; im.drawHeight=460
    story.extend([im,Spacer(1,5),p('Overview uses the saved route geometry and existing local map rendering. Start/end markers are shown on the map. Map data © OpenStreetMap contributors.','SmallRoute'),PageBreak(),p('Numbered driving directions','RouteTitle'),p(esc(title)),p('Distance is travel after each instruction. Source rounding is retained: 0 ft does not mean an omitted instruction. Unnamed roads remain unnamed.','SmallRoute')])
    rows=[[p('<b>Step</b>'),p('<b>Instruction / road</b>'),p('<b>Go</b>')]]
    for i,m in enumerate(d['maneuvers'],1):
        road=m['road'].strip() or 'Road name not supplied'
        cell=p('<b>'+esc(m['instruction'])+'</b><br/>'+esc(road))
        rows.append([p(str(i)),cell,p('<b>'+esc(m['distance_display'])+'</b>')])
    t=Table(rows,colWidths=[40,399,65],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')),('LINEBELOW',(0,0),(-1,0),1,colors.black),('LINEBELOW',(0,1),(-1,-1),.4,colors.HexColor('#777777')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),5)]))
    story.extend([t,Spacer(1,10),p(esc(d.get('source_caveat','Source: local OsmAnd OBF; offline snapshot. Integrity: verified download/ZIP CRC receipt and current size; no fresh full-map hash.')),'SmallRoute'),p('<b>END:</b> '+esc(d['end_label'])),p('All '+str(len(d['maneuvers']))+' saved maneuvers are included, including engine-muted prompts. Lane/mute codes and exact original descriptions are preserved in the accompanying route JSON; lane codes are not expanded or guessed.','SmallRoute')])
    def page(c,doc):
        c.saveState();c.setFillColor(colors.black);c.setFont('Helvetica',9)
        c.drawString(54,762,'DRIVING DIRECTIONS');c.line(54,751,558,751)
        c.drawString(54,28,'Offline snapshot '+d['snapshot']+' | No live traffic');c.drawRightString(558,28,'Page '+str(doc.page));c.restoreState()
    SimpleDocTemplate(str(output),pagesize=letter,rightMargin=54,leftMargin=54,topMargin=52,bottomMargin=48,title=title,author='Local route print pack').build(story,onFirstPage=page,onLaterPages=page)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('route_json',type=Path);a.add_argument('output_pdf',type=Path);args=a.parse_args()
    render(json.loads(args.route_json.read_text()),args.output_pdf)
