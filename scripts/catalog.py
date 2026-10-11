"""Emote Wheel catalog discovery and publication. Python stdlib only."""
import argparse, base64, hashlib, json, os, re, struct, time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.guildwars2.com/v2/emotes?ids=all'
WIKI = 'https://wiki.guildwars2.com/wiki/Emote'
WIKI_API = 'https://wiki.guildwars2.com/api.php?action=parse&page=Emote&prop=text&format=json'
CATEGORIES = {'Social','Emociones','Bailes','Poses','Actividades','Magia y efectos','Especiales'}
ICONS = {'hand','bow','music','star','clap','smile','tear','check','cross','question','arrow','chair','moon','flag','spark','sword','book','cup','heart'}
COMMAND = re.compile(r'^[a-z]{1,32}$')
MAX_BYTES = 2097152


def fetch(url, *, token=None, method='GET', payload=None, limit=MAX_BYTES):
    headers = {'User-Agent':'EmoteWheelCatalog/0.2 (https://github.com/zioreth/emote-wheel-catalog; contact: GitHub issues)', 'Accept':'application/json'}
    if token:
        headers.update(Authorization='Bearer '+token, **{'X-GitHub-Api-Version':'2022-11-28'})
    body = json.dumps(payload).encode() if payload is not None else None
    if body: headers['Content-Type']='application/json'
    for attempt in range(3):
        try:
            with urlopen(Request(url, data=body, headers=headers, method=method), timeout=30) as response:
                data=response.read(limit+1)
                if len(data)>limit: raise ValueError('Response exceeds size limit')
                return data
        except HTTPError as error:
            if error.code not in (429,500,502,503,504) or attempt==2: raise
        except (TimeoutError, OSError):
            if attempt==2: raise
        time.sleep(2**attempt)


class EmoteTable(HTMLParser):
    def __init__(self):
        super().__init__(); self.commands=set(); self.groups={}; self.row=[]; self.cell=None
    def handle_starttag(self, tag, attrs):
        if tag=='tr': self.row=[]
        if tag in ('td','th'): self.cell=[]
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip()); self.cell=None
        if tag=='tr' and len(self.row)>=4:
            match=re.match(r'^/([a-z]{1,32})(?![a-z])',self.row[0])
            if match:
                command=match[1];self.commands.add(command);self.groups[command]=set(re.findall(r'/([a-z]{1,32})(?![a-z])',self.row[0]))


def wiki_commands(html, known=()):
    parser=EmoteTable(); parser.feed(html)
    if len(parser.commands)<30: raise ValueError('Wiki table changed or incomplete; no silent empty result')
    return {c for c in parser.commands if not parser.groups[c].intersection(known)}


def api_commands(data):
    if not isinstance(data,list) or len(data)<4: raise ValueError('API schema or coverage changed')
    result={}
    for row in data:
        if not isinstance(row,dict) or not isinstance(row.get('commands'),list) or not row['commands']: raise ValueError('Invalid API emote')
        # The first command is the canonical English command; localized aliases are not separate emotes.
        command=row['commands'][0].removeprefix('/')
        if COMMAND.fullmatch(command): result[command]=row
    if not result: raise ValueError('No canonical API commands')
    return result


def png_valid(value):
    if not isinstance(value,str) or len(value)>180000: raise ValueError('Invalid image size')
    data=base64.b64decode(value,validate=True)
    if len(data)<24 or data[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError('Icon must be PNG')
    width,height=struct.unpack('>II',data[16:24])
    if not (16<=width<=256 and 16<=height<=256): raise ValueError('Icon must be 16..256 pixels')


def validate(entry):
    command=entry.get('Command','')
    if not COMMAND.fullmatch(command): raise ValueError('Invalid command')
    if entry.get('Reviewed') is not True: raise ValueError(command+': review required (Reviewed=true)')
    for key in ('Name','English'):
        value=entry.get(key)
        if not isinstance(value,str) or not value.strip() or len(value)>100 or any(ord(c)<32 for c in value): raise ValueError(command+': invalid '+key)
    for key in ('German','French','Aliases','UnlockItem'):
        value=entry.get(key)
        if value is not None and (not isinstance(value,str) or len(value)>500 or any(ord(c)<32 for c in value)): raise ValueError(command+': invalid '+key)
    if entry.get('Category') not in CATEGORIES or entry.get('Icon') not in ICONS or not isinstance(entry.get('Unlock'),bool): raise ValueError(command+': metadata required')
    if entry['Unlock'] and not entry.get('UnlockItem'): raise ValueError(command+': unlock requirement missing')
    if not entry.get('Sources'): raise ValueError(command+': source attribution required')
    png_valid(entry.get('ImagePng'))
    return entry


def entries():
    result=[]; seen=set(json.loads((ROOT/'baseline.json').read_text()))
    for file in sorted((ROOT/'entries').glob('*.json')):
        value=validate(json.loads(file.read_text(encoding='utf-8')))
        if file.stem!=value['Command'] or value['Command'] in seen: raise ValueError('Duplicate/baseline command: '+file.name)
        seen.add(value['Command']);result.append(value)
    if len(result)>250: raise ValueError('Too many remote additions')
    return result


class GitHub:
    def __init__(self):
        self.repo=os.environ['GITHUB_REPOSITORY'];self.token=os.environ['GITHUB_TOKEN']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',self.repo): raise ValueError('Invalid repository')
        self.base='https://api.github.com/repos/'+self.repo
    def call(self,path,method='GET',payload=None):
        data=fetch(self.base+path,token=self.token,method=method,payload=payload,limit=8*MAX_BYTES)
        return json.loads(data) if data else None
    def pages(self,path):
        result=[]
        for page in range(1,101):
            batch=self.call(path+('&' if '?' in path else '?')+'per_page=100&page='+str(page));result.extend(batch)
            if len(batch)<100:return result
        raise ValueError('Pagination safety limit reached')
    def put_file(self,branch,path,data,message):
        sha=None
        try:sha=self.call('/contents/'+path+'?ref='+quote(branch,safe=''))['sha']
        except HTTPError as error:
            if error.code!=404:raise
        payload={'branch':branch,'message':message,'content':base64.b64encode(data).decode()}
        if sha:payload['sha']=sha
        return self.call('/contents/'+path,'PUT',payload)
    def ensure_branch(self,branch,base):
        try:self.call('/git/ref/heads/'+quote(branch,safe=''))
        except HTTPError as error:
            if error.code!=404:raise
            sha=self.call('/git/ref/heads/'+quote(base,safe=''))['object']['sha']
            self.call('/git/refs','POST',{'ref':'refs/heads/'+branch,'sha':sha})


def notify_mention():
    user=os.environ.get('REVIEWER','').strip()
    return '@'+user+'\n\n' if re.fullmatch(r'[A-Za-z0-9-]{1,39}',user) else ''


def failure_issue(github, errors, kind="discovery"):
    marker='<!-- emote-wheel-monitor-health-'+kind+' -->'
    issues=github.pages('/issues?state=open')
    existing=next((i for i in issues if marker in (i.get('body') or '')),None)
    if errors and existing is None:
        body=marker+'\n'+notify_mention()+'La búsqueda no pudo completar todas las fuentes. El catálogo publicado permanece intacto.\n\n'+'\n'.join('- '+e for e in errors)+'\n\nRevisa el registro de Actions. No se repetirán avisos mientras esta incidencia siga abierta.'
        github.call('/issues','POST',{'title':'Emote Wheel: revisar búsqueda de novedades','body':body})
    elif not errors and existing:
        github.call('/issues/'+str(existing['number']),'PATCH',{'state':'closed','state_reason':'completed'})


def proposal(command, api_row=None):
    value={'Command':command,'Name':command,'English':command,'German':None,'French':None,'Icon':'star','Unlock':True,'Category':'Especiales','Aliases':'','UnlockItem':'PENDIENTE: confirmar requisito','ImagePng':'','Reviewed':False,'Sources':[WIKI]}
    if api_row:
        value['Sources'].append('https://api.guildwars2.com/v2/emotes/'+quote(api_row['id']))
        ids=api_row.get('unlock_items',[])
        if ids:
            value['UnlockItem']='Item '+str(ids[0])
            try:
                item=json.loads(fetch('https://api.guildwars2.com/v2/items/'+str(int(ids[0]))))
                icon=item.get('icon','')
                if re.fullmatch(r'https://render\.guildwars2\.com/file/[A-Fa-f0-9]+/[0-9]+\.png',icon):
                    data=base64.b64encode(fetch(icon,limit=135000)).decode();png_valid(data)
                    value['ImagePng']=data;value['Sources'].append(icon)
            except (OSError,ValueError,KeyError):pass  # Missing artwork remains an explicit review task.
    return value


def discover(live=False):
    known=set(json.loads((ROOT/'baseline.json').read_text()))|{p.stem for p in (ROOT/'entries').glob('*.json')}
    found={};errors=[]
    try:found.update(api_commands(json.loads(fetch(API))))
    except Exception as error:errors.append('API: '+type(error).__name__)
    try:
        html=json.loads(fetch(WIKI_API,limit=8*MAX_BYTES))['parse']['text']['*']
        for command in wiki_commands(html,known):found.setdefault(command,None)
    except Exception as error:errors.append('Wiki: '+type(error).__name__+(' HTTP '+str(error.code) if isinstance(error,HTTPError) else ''))
    candidates=sorted(set(found)-known)
    report={'candidates':candidates,'errors':errors,'sources':[API,WIKI]}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not live:return report
    github=GitHub();default=github.call('')['default_branch']
    pulls=github.pages('/pulls?state=all')
    for command in candidates:
        branch='catalog/'+command
        # Closed PR means explicitly rejected; existing PR edits are never overwritten.
        if any(p['head']['ref']==branch for p in pulls):continue
        github.ensure_branch(branch,default)
        value=proposal(command,found[command]);data=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
        github.put_file(branch,'entries/'+command+'.json',data,'Proponer emote /'+command)
        body=notify_mention()+'Detectado `/'+command+'`. Propuesta pendiente de revisión; no se publicará automáticamente.\n\n- [ ] Confirmar comando, nombre, categoría y desbloqueo.\n- [ ] Revisar traducciones e ícono (ImagePng).\n- [ ] Cambiar Reviewed a true y ejecutar Validate manualmente en esta rama.\n- [ ] Fusionar para publicar, o cerrar para descartar.\n\nFuentes:\n'+'\n'.join(value['Sources'])+'\n\nSi falta el ícono, usa `python scripts/catalog.py icon entries/'+command+'.json ruta/al/icono.png`. La cuenta GitHub Actions no genera por sí misma imágenes nuevas.'
        github.call('/pulls','POST',{'title':'Revisar nuevo emote: /'+command,'head':branch,'base':default,'body':body})
    failure_issue(github,errors)
    if errors:
        (ROOT/'.health-reported').touch()
        if errors == ['Wiki: HTTPError HTTP 403']:
            report['status']='partial'
            message='Cobertura parcial: la API respondió; la wiki sigue bloqueada (HTTP 403). La incidencia permanece abierta. No se confirma ausencia de emotes nuevos fuera de la API.'
            print('::warning title=Cobertura parcial del catálogo::'+message)
            if os.environ.get('GITHUB_STEP_SUMMARY'):
                with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as summary:
                    summary.write('## Cobertura parcial\n\n'+message+'\n\nPropuestas detectadas: '+str(len(candidates))+'\n')
            return report
        raise RuntimeError('One or more discovery sources failed; health issue recorded')
    report['status']='complete'
    return report


def publish():
    values=entries();github=GitHub();default=github.call('')['default_branch']
    github.ensure_branch('published',default)
    old=None
    try:
        old=json.loads(base64.b64decode(github.call('/contents/catalog.json?ref=published')['content']))
    except HTTPError as error:
        if error.code!=404:raise
    if old and old.get('Entries')==values:
        failure_issue(github,[],kind='publication');return
    if old:
        previous={e['Command']:e for e in old['Entries']}
        current={e['Command']:e for e in values}
        if any(current.get(k)!=v for k,v in previous.items()):raise ValueError('Published entries are immutable in schema 1; removals/edits require coordinated migration')
    payload={'Schema':1,'Revision':max(int(time.time()),(old or {}).get('Revision',0)+1),'Entries':values}
    data=(json.dumps(payload,ensure_ascii=False,indent=2)+'\n').encode()
    if len(data)>MAX_BYTES:raise ValueError('Published catalog exceeds client size limit')
    github.put_file('published','catalog.json',data,'Publicar catálogo aprobado')
    failure_issue(github,[],kind='publication')
    print('https://raw.githubusercontent.com/'+github.repo+'/published/catalog.json')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['discover','validate','publish','icon']);parser.add_argument('--live',action='store_true');parser.add_argument('files',nargs='*');args=parser.parse_args()
    if args.mode=='discover':discover(args.live)
    elif args.mode=='validate':print('Validated entries:',len(entries()))
    elif args.mode=='publish':publish()
    else:
        if len(args.files)!=2:parser.error('icon requires entry.json and icon.png')
        entry,image=map(Path,args.files);value=json.loads(entry.read_text(encoding='utf8'));encoded=base64.b64encode(image.read_bytes()).decode();png_valid(encoded);value['ImagePng']=encoded;entry.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
