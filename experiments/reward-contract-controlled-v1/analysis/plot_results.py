"""Render existing saved results only; requires the already bundled Pillow."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
summary = json.loads((ROOT/'results/comparison/summary.json').read_text())
methods = [('llm','LLM'),('rules','Fixed rules'),('fixed_E','Always equality (E)'),('fixed_V','Always validity (V)'),('fixed_null','Always abstain')]
records = []
for key,label in methods:
    d=summary['conditions'][key]; c=d['binary_confusion']
    records.append({'method':key,'label':label,'correct':c['TP']+c['TN'],'errors':c['FP']+c['FN'],'unknown':c['Unknown'],'witness_supported_correct':d['witness_supported_correct_cells']})
(ROOT/'figures/chart-data.json').write_text(json.dumps({'denominator':24,'records':records,'source':'results/comparison/summary.json','unit':'8 nonnull descriptions crossed with 3 shared programs; only 6 distinct semantic/program combinations','excluded':'4 U descriptions and their 12 administrative cells'},indent=2)+'\n')
W,H=1600,1020
im=Image.new('RGB',(W,H),'#fbfcfe');draw=ImageDraw.Draw(im)
regular='/System/Library/Fonts/Supplemental/Arial.ttf'
bold='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def font(n,b=False): return ImageFont.truetype(bold if b else regular,n)
def text(x,y,s,n=25,c='#233146',b=False): draw.text((x,y),s,font=font(n,b),fill=c)
colors={'correct':'#247e83','errors':'#c3564b','unknown':'#b8c2cf'}
text(65,48,'LLM contracts improve coverage in this controlled set',40,b=True)
text(65,109,'Same frozen checker. Fixed descriptions, rules and prompts. No outcome-based tuning.',24,c='#526074')
text(65,174,'METHOD',20,c='#526074',b=True)
text(365,174,'BINARY DECISIONS / 24',20,c='#526074',b=True)
text(1305,166,'WITNESS-SUPPORTED',18,c='#526074',b=True)
text(1305,191,'CORRECT / 24',18,c='#526074',b=True)
x0=365;width=880;y0=245;gap=106
for n in [0,6,12,18,24]:
 x=x0+width*n/24
 draw.line((x,230,x,755),fill='#e2e7ee',width=2)
 text(x-9,772,str(n),20,c='#526074')
for i,r in enumerate(records):
 y=y0+i*gap
 text(65,y+14,r['label'],26,b=i==0)
 cursor=x0
 for k in ['correct','errors','unknown']:
  value=r[k]
  if not value: continue
  w=width*value/24
  draw.rectangle((cursor,y,cursor+w,y+61),fill=colors[k])
  label=str(value); tw=draw.textbbox((0,0),label,font=font(26,True))[2]
  text(cursor+(w-tw)/2,y+14,label,26,c='white' if k!='unknown' else '#253247',b=True)
  cursor+=w
 text(1360,y+13,str(r['witness_supported_correct'])+'/24',28,b=True)
legend_x=365
for k,label in [('correct','Correct binary label'),('errors','FP or FN'),('unknown','Unknown')]:
 draw.rectangle((legend_x,831,legend_x+25,856),fill=colors[k]);text(legend_x+37,829,label,22)
 legend_x+=330 if k=='correct' else 240
text(65,899,'24 cells = 8 descriptions x 3 shared programs; they repeat only 6 semantic/program combinations.',22,c='#526074')
text(65,934,'Four U descriptions are excluded. Always-E has 4 additional label-correct alarms with invalid gold witnesses.',22,c='#526074')
text(65,969,'Synthetic policy controls; no claim of new upstream bugs or independently demonstrated real-project gains.',21,c='#526074')
im.save(ROOT/'figures/downstream-comparison.png')
print(json.dumps({'figure':'figures/downstream-comparison.png','size':[W,H],'data_records':records}))
