import base64, copy, json, struct, sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import catalog

class Tests(unittest.TestCase):
 def good(self):
  return {'Command':'testgesture','Name':'Prueba','English':'Test','Icon':'star','Unlock':True,'UnlockItem':'Item 1','Category':'Social','ImagePng':base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'\x00'*8+struct.pack('>II',64,64)).decode(),'Reviewed':True,'Sources':['https://wiki.guildwars2.com/wiki/Emote']}
 def test_valid(self):catalog.validate(self.good())
 def test_pending_rejected(self):
  value=self.good();value['Reviewed']=False
  with self.assertRaises(ValueError):catalog.validate(value)
 def test_commands(self):
  for cmd in ('dance\n/say hello','/dance','dance hello','x'*33,''):
   value=self.good();value['Command']=cmd
   with self.assertRaises(ValueError):catalog.validate(value)
 def test_png_bounds(self):
  value=self.good();value['ImagePng']=base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'\x00'*8+struct.pack('>II',999999,64)).decode()
  with self.assertRaises(ValueError):catalog.validate(value)
 def test_missing_art(self):
  value=self.good();value['ImagePng']=''
  with self.assertRaises(ValueError):catalog.validate(value)
 def test_api_aliases(self):
  rows=[{'commands':['/'+c,'/francais'],'id':c} for c in ('dance','wave','sit','laugh')]
  self.assertEqual(set(catalog.api_commands(rows)),{'dance','wave','sit','laugh'})
 def test_wiki_does_not_scan_prose(self):
  rows=''.join('<tr><td><b>/emote'+chr(97+i//26)+chr(97+i%26)+'</b></td><td>/alias</td><td>German</td><td>Spanish</td></tr>' for i in range(40))
  commands=catalog.wiki_commands('<p>/quit /say</p>'+rows)
  self.assertEqual(len(commands),40);self.assertNotIn('alias',commands);self.assertNotIn('quit',commands)
 def test_wiki_breakage(self):
  with self.assertRaises(ValueError):catalog.wiki_commands('<html>Maintenance</html>')
 def test_notification_deduplication(self):
  class GH:
   def __init__(self):self.calls=[]
   def pages(self,path):return [{'number':1,'body':'<!-- emote-wheel-monitor-health-discovery -->'}]
   def call(self,*args):self.calls.append(args)
  gh=GH();catalog.failure_issue(gh,['API failed']);self.assertFalse(gh.calls)
  catalog.failure_issue(gh,[]);self.assertEqual(gh.calls[0][2]['state'],'closed')
 def test_discovery_keeps_partial_failure_visible(self):
  with patch.object(catalog,'fetch',side_effect=OSError('offline')):
   report=catalog.discover(False)
  self.assertEqual(len(report['errors']),2)
 def test_proposal_never_approved(self):
  value=catalog.proposal('newemote');self.assertFalse(value['Reviewed'])
  with self.assertRaises(ValueError):catalog.validate(value)

 def test_closed_proposal_is_not_recreated(self):
  class GH:
   def call(self,path,*args):return {'default_branch':'main'}
   def pages(self,path):return [{'head':{'ref':'catalog/newgesture'}}] if path.startswith('/pulls') else []
   def ensure_branch(self,*args):raise AssertionError('Must not recreate a rejected proposal')
  with patch.object(catalog,'fetch',return_value=b'{"parse":{"text":{"*":""}}}'),patch.object(catalog,'api_commands',return_value={'newgesture':None}),patch.object(catalog,'wiki_commands',return_value=set()),patch.object(catalog,'GitHub',return_value=GH()):
   self.assertEqual(catalog.discover(True)['candidates'],['newgesture'])
 def test_publication_refuses_removal(self):
  class GH:
   def call(self,path,*args):
    if not path:return {'default_branch':'main'}
    return {'content':base64.b64encode(json.dumps({'Entries':[{'Command':'existing'}],'Revision':1}).encode()).decode()}
   def ensure_branch(self,*args):pass
  with patch.object(catalog,'GitHub',return_value=GH()),patch.object(catalog,'entries',return_value=[]):
   with self.assertRaises(ValueError):catalog.publish()

if __name__=='__main__':unittest.main()
