# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import bot
import library_access as library
import citation_links
import multistate_routing as trip
import named_routing
from local_visuals import route_map
from local_visuals.units import distance

class Core(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'guides').mkdir()
        (self.root/'guides/storage.txt').write_text('SYNTHETIC reference: Store amber beacon batteries in the dry blue cabinet. Inspect the cabinet seal monthly. '*5)
        (self.root/'guides/garden.txt').write_text('SYNTHETIC reference: Plant fictional moon carrots in purple sand. This is a software fixture, not real advice. '*4)
    def test_offline_index_retrieve_read(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Network prohibited')):
            result=bot.build(self.root)
            self.assertEqual(result['indexed_files'],2)
            found=bot.retrieve(self.root,'Where should beacon batteries be stored?')
            self.assertIn('storage.txt',found['sources'][0]['source'])
            self.assertIn('dry blue cabinet',found['sources'][0]['text'])
            self.assertEqual(found['sources'][0]['id'],'R1')
            self.assertIn('storage.txt',bot.retrieve(self.root,'Read: guides/storage.txt')['sources'][0]['source'])
            self.assertFalse(bot.retrieve(self.root,'Search: quuxnonexistent')['sources'])
        with self.assertRaises(ValueError):
            bot.build(self.root)
    def test_reject_paths(self):
        (self.root/'guides/link.txt').symlink_to(self.root/'guides/storage.txt')
        (self.root/'credentials.txt').write_text('synthetic protected fixture')
        for name in ['../outside.txt','guides/link.txt','credentials.txt']:
            with self.assertRaises(ValueError):
                library.safe(self.root,name)
        self.assertNotIn('guides/link.txt',library.catalog(self.root))
    def test_ranking_and_html(self):
        self.assertGreater(library.title_rank('Battery storage',['battery']),library.title_rank('Category:Battery',['battery']))
        from reference_helpers import clean
        self.assertEqual(clean('<p>amber</p><script>bad()</script><style>x</style>'),'amber')
    def test_street_fallback_and_parser(self):
        r=trip.parse('Directions from 10 Fictional Lane, Exampleville, Ohio to 20 Imaginary Road, Sampletown, Indiana with fuel stops every 100 miles')
        self.assertEqual(r['endpoints'][0]['house'],'10')
        self.assertEqual(r['endpoints'][0]['city'],'Exampleville')
        self.assertEqual(r['fuel_interval']['value'],100)
        pin,label=trip.resolve({}, {'counts':[1,1], 'streets':[['Fictional Lane','1','2']]})
        self.assertEqual(pin,[1.0,2.0])
        self.assertIn('approximate street',label)
        pin,label=trip.resolve({}, {'counts':[0,0]})
        self.assertIsNone(pin)
        self.assertIn('no town center',label)
        pin,label=trip.resolve({}, {'counts':[1,1], 'matches':[['building','1','2']], 'streets':[['Fictional Lane','3','4']]})
        self.assertEqual(pin,[1.0,2.0])
        self.assertIn('entrance unverified',label)
    def test_engine_geometry_and_units(self):
        raw='<test route_base="false">\n<segment id="1" name="Synthetic Road" distance="10" turn="C" description="Continue" />\n</test>\nRoute is 1 segments\nGEOMSEG\t0\t64\t0\t1\nPOINT\t0\t0\t1\t2\nPOINT\t0\t1\t1.001\t2.001\n'
        segments=named_routing.parse_engine(raw)
        geometry=route_map.parse_geometry(raw,segments)
        self.assertEqual(len(geometry[0]['points']),2)
        self.assertIn('native_bounds31',route_map.native_layout({'geometry':geometry}))
        with self.assertRaises(ValueError):
            route_map.parse_geometry(raw.replace('POINT\t0\t1','POINT\t0\t3'),segments)
        self.assertEqual(distance(1609.344,total=True),'1.00 mi')

class Documents(unittest.TestCase):
    def test_pdf_retrieval_citation_and_print(self):
        from reportlab.pdfgen.canvas import Canvas
        from PIL import Image
        from local_visuals import print_route_formatter as formatter
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'guides').mkdir()
            pdf=root/'guides/synthetic.pdf'
            c=Canvas(str(pdf))
            c.drawString(40,700,'SYNTHETIC beacon storage: use the blue cabinet. Software fixture only.')
            c.showPage();c.drawString(40,700,'SYNTHETIC second page: amber marker. Software fixture only.');c.save()
            with patch.object(socket.socket,'connect',side_effect=AssertionError('Network prohibited')):
                bot.build(root)
                result=bot.retrieve(root,'Search: beacon storage')
                self.assertIn('PDF page 1',result['sources'][0]['source'])
                old=citation_links.ALLOWED
                try:
                    citation_links.ALLOWED=frozenset(['guides/synthetic.pdf'])
                    url=citation_links.source_url(result['sources'][0]['source'],root)
                    self.assertTrue(url.endswith('#page=1'))
                    with citation_links.open_document(root,'guides/synthetic.pdf') as stream:
                        self.assertEqual(stream.read(4),b'%PDF')
                    with self.assertRaises(ValueError):
                        citation_links.open_document(root,'guides/not-allowed.pdf')
                    self.assertIn('Local sources:',citation_links.render('Source [R1]',result['sources'],root))
                finally:
                    citation_links.ALLOWED=old
                png=root/'synthetic.png';Image.new('RGB',(850,700),'white').save(png)
                data={'status':'ok','verified_source':True,'start_label':'SYNTHETIC START','end_label':'SYNTHETIC END','distance_display':'1.00 mi','eta_display':'2 minutes','snapshot':'SYNTHETIC','map_png':str(png),'maneuvers':[{'instruction':'Continue','road':'Fictional Road','distance_display':'0 ft'},{'instruction':'Arrive','road':'','distance_display':'1.00 mi'}],'source_caveat':'Synthetic fixture; not an engine-verified route.'}
                output=root/'route.pdf';formatter.render(data,output)
                text=subprocess.check_output(['pdftotext',str(output),'-'],text=True)
                self.assertIn('SYNTHETIC START',text)
                self.assertIn('0 ft',text)
                self.assertIn('Road name not supplied',text)
                data['verified_source']=False
                with self.assertRaises(ValueError):
                    formatter.render(data,output)

if __name__=='__main__':
    unittest.main()
