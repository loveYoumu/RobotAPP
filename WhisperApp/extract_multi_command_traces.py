import argparse,collections,json,math,time
from pathlib import Path
import torch,whisper
from runtime_env import ensure_ffmpeg_on_path

def shp(x):
 if torch.is_tensor(x):return list(x.shape)
 if isinstance(x,(list,tuple)):return [shp(y) for y in x if torch.is_tensor(y)]
 return None

def main():
 ensure_ffmpeg_on_path()
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--model',default='small');p.add_argument('--model-dir',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
 manifest=Path(a.manifest);items=[json.loads(x) for x in manifest.read_text(encoding='utf-8').splitlines() if x]
 for item in items:
  audio=Path(item['audio']);item['audio']=str(audio if audio.is_absolute() else (manifest.parent/audio).resolve())
 out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);model=whisper.load_model(a.model,device='cuda',download_root=a.model_dir);summaries=[]
 for item in items:
  events=[];handles=[]
  def make(name,kind):
   def hook(mod,inputs,output):
    e={'index':len(events),'module':name,'kind':kind,'input_shape':shp(inputs[0]) if inputs else None,'output_shape':shp(output)}
    if kind=='Linear':
     x=inputs[0];e['gemm']={'M':math.prod(x.shape[:-1]),'K':x.shape[-1],'N':mod.weight.shape[0]}
    elif kind=='Conv1d':e['conv1d']={'in_channels':mod.in_channels,'out_channels':mod.out_channels,'kernel':mod.kernel_size[0],'stride':mod.stride[0]}
    elif kind=='MultiHeadAttention':e['attention']={'heads':mod.n_head,'head_dim':mod.query.out_features//mod.n_head}
    events.append(e)
   return hook
  for name,mod in model.named_modules():
   kind=mod.__class__.__name__
   if kind in ('Linear','Conv1d','LayerNorm','MultiHeadAttention','ResidualAttentionBlock'):handles.append(mod.register_forward_hook(make(name,kind)))
  st=time.perf_counter();res=model.transcribe(item['audio'],language='zh',task='transcribe',fp16=True,temperature=0.0,beam_size=5,condition_on_previous_text=False,verbose=False);torch.cuda.synchronize();elapsed=time.perf_counter()-st
  for h in handles:h.remove()
  d=out/item['id'];d.mkdir(exist_ok=True)
  with (d/'operator_events.jsonl').open('w') as f:
   for e in events:f.write(json.dumps(e,ensure_ascii=False)+'\n')
  kinds=dict(collections.Counter(e['kind'] for e in events));gemms=[e['gemm'] for e in events if e['kind']=='Linear'];shapes=collections.Counter((g['M'],g['N'],g['K']) for g in gemms);macs=sum(g['M']*g['N']*g['K'] for g in gemms)
  s={'id':item['id'],'reference':item['reference'],'hypothesis':res['text'].strip(),'duration_s':item['duration_s'],'inference_s':elapsed,'event_count':len(events),'kind_counts':kinds,'atomic_tasks':3+kinds.get('Conv1d',0)+kinds.get('LayerNorm',0)+kinds.get('Linear',0)+kinds.get('MultiHeadAttention',0),'gemm_calls':len(gemms),'unique_gemm_shapes':len(shapes),'linear_macs':macs,'gemm_shapes':[{'M':k[0],'N':k[1],'K':k[2],'calls':v} for k,v in sorted(shapes.items())]};(d/'summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');summaries.append(s);print(json.dumps({'id':s['id'],'text':s['hypothesis'],'events':s['event_count'],'gemms':s['gemm_calls'],'macs':s['linear_macs']},ensure_ascii=False),flush=True)
 (out/'multi_command_summary.json').write_text(json.dumps({'status':'PASS','model':a.model,'commands':summaries},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
