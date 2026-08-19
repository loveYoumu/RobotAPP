import argparse, collections, json, math, time
from pathlib import Path
import torch, whisper
from runtime_env import ensure_ffmpeg_on_path

def shape(x):
    if torch.is_tensor(x): return list(x.shape)
    if isinstance(x,(list,tuple)): return [shape(y) for y in x if torch.is_tensor(y)]
    return None

def main():
    ensure_ffmpeg_on_path()
    p=argparse.ArgumentParser();p.add_argument('--audio',required=True);p.add_argument('--model',default='small');p.add_argument('--model-dir',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    model=whisper.load_model(a.model,device='cuda',download_root=a.model_dir)
    events=[]; handles=[]
    selected=('Linear','Conv1d','LayerNorm','MultiHeadAttention','ResidualAttentionBlock')
    def hook(name,kind,module):
        def fn(mod,inputs,output):
            rec={'index':len(events),'module':name,'kind':kind,'input_shape':shape(inputs[0]) if inputs else None,'output_shape':shape(output)}
            if kind=='Linear':
                x=inputs[0]; rec['gemm']={'M':math.prod(x.shape[:-1]),'K':x.shape[-1],'N':mod.weight.shape[0]}
            elif kind=='Conv1d':
                rec['conv1d']={'in_channels':mod.in_channels,'out_channels':mod.out_channels,'kernel':mod.kernel_size[0],'stride':mod.stride[0]}
            elif kind=='MultiHeadAttention': rec['attention']={'heads':mod.n_head,'head_dim':mod.query.out_features//mod.n_head}
            events.append(rec)
        return fn
    for name,module in model.named_modules():
        kind=module.__class__.__name__
        if kind in selected: handles.append(module.register_forward_hook(hook(name,kind,module)))
    start=time.perf_counter(); result=model.transcribe(a.audio,language='zh',task='transcribe',fp16=True,temperature=0.0,beam_size=5,condition_on_previous_text=False,verbose=False);torch.cuda.synchronize();elapsed=time.perf_counter()-start
    for h in handles:h.remove()
    sig=collections.Counter()
    examples={}
    for e in events:
        extra=e.get('gemm') or e.get('conv1d') or e.get('attention') or {}
        key=json.dumps([e['kind'],e['module'],e['input_shape'],e['output_shape'],extra],sort_keys=True,ensure_ascii=False)
        sig[key]+=1;examples[key]=e
    aggregates=[]
    for key,count in sig.most_common():
        x=dict(examples[key]);x.pop('index',None);x['calls']=count;aggregates.append(x)
    with (out/'operator_events.jsonl').open('w',encoding='utf-8') as f:
        for e in events:f.write(json.dumps(e,ensure_ascii=False)+'\n')
    summary={'status':'PASS','model':a.model,'audio':str(Path(a.audio).resolve()),'text':result['text'].strip(),'inference_s':elapsed,'event_count':len(events),'kind_counts':dict(collections.Counter(e['kind'] for e in events)),'unique_signatures':len(aggregates),'aggregates':aggregates}
    (out/'operator_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='aggregates'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
