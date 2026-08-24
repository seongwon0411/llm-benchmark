from __future__ import annotations
import argparse,json,sqlite3,shutil,tempfile,zipfile,sys,os,copy
from pathlib import Path
from workbench.common import HERE,load_json,reset_workspace,hash_tree
from workbench.lmstudio import scan_models,ensure_imported,start_server,load_model,unload_all,chat_messages,GPUMonitor
from workbench.tools import TOOL_SCHEMAS,execute_tool,inspect_pptx_structure
from workbench.graders import grade_task,judge_eligible,judge_score_cap
from workbench.judge_context import build_reference_packet
from workbench.reporting import write_reports

# Windows PowerShell 5.1 can expose a cp949 console. Never let diagnostics crash a task.
os.environ.setdefault('PYTHONUTF8','1')
os.environ.setdefault('PYTHONIOENCODING','utf-8')
for _stream in (sys.stdout,sys.stderr):
    try:_stream.reconfigure(errors='backslashreplace')
    except Exception:pass

VERSION='7.2.2'
CFG=load_json(HERE/'config.json')
TASKS=load_json(HERE/'tasks.json')
SELECTED=load_json(HERE/'selected_models.json')
FIXTURES=HERE/'fixtures'
RUNS=HERE/CFG['runs_dir']
OUT=HERE/CFG['results_dir']/'work'
DB=OUT/'benchmark.db'

SYSTEM='''당신은 실제 업무를 끝까지 수행하는 로컬 AI 에이전트다. 설명만 하지 말고 workspace의 실제 파일을 읽고, 요구된 산출물을 직접 생성/수정하고, 실행/검증해야 한다. 근거 없는 사실이나 숫자는 만들지 마라.

[도구 사용 규칙 — 모든 모델에 동일]
1) 모든 path는 workspace 기준 상대경로만 사용한다. 예: `brief.md`, `tests`, `slides.json`. `/workspace/...`, `/root/workspace/...`, `C:\\...` 같은 절대경로를 만들지 마라.
2) 먼저 `list_files`로 실제 파일명을 확인하고, 목록에 없는 경로나 파일을 추측하지 마라.
3) 텍스트/CSV/코드는 `read_text`, 근거 행번호가 필요하면 `read_with_lines`를 쓴다.
4) Excel(.xlsx)은 `read_excel` 또는 `inspect_xlsx`로 읽는다. `read_text`로 xlsx를 읽지 마라.
5) 텍스트/코드 생성은 `write_text`, 기존 코드의 정확한 일부 수정은 `edit_file`을 쓸 수 있다.
6) `write_text`로 pptx/xlsx/png 같은 바이너리 파일을 직접 만들면 안 된다.
7) PPT 과제는 `create_pptx`를 우선 사용한다. 권장 절차: 원자료 읽기 → 계산/근거 확인 → 슬라이드별 한 문장 핵심 메시지 설계 → `create_pptx`에 `slides` 배열 직접 전달 → `inspect_pptx`의 표 셀/차트 데이터/design_score/quality 경고 확인 → 치명적 경고가 있으면 재생성. `spec_path`는 fallback이다.
8) PPT는 '파일 생성'이 아니라 실제 임원/의사결정 보고 품질을 목표로 한다. 표지 이후 각 슬라이드는 `takeaway`를 원칙적으로 포함하고, 숫자 중심 슬라이드는 `kpis`나 차트, 리스크/조치 슬라이드는 실제 값이 채워진 table, 사건 흐름은 timeline을 사용한다. 제목+한 줄만 있는 빈 페이지, 일반론만 있는 결론, 기본 bullet 나열만 반복하는 구성을 피한다. 마지막 장은 `layout: decision`과 `callout`을 활용해 권고/판단과 조건을 명확히 연결한다.
9) table 셀은 문자열/숫자를 권장한다. 강조가 필요하면 `{"value":"내용","bold":true,"align":"center","tone":"high|medium|low"}` 형식을 사용할 수 있다. Python dict 자체를 문자열로 넣지 마라.
10) `run_python`은 사용자 정의 계산/처리나 `create_pptx`로 표현하기 어려운 경우에 사용할 수 있다. Python 환경에는 python-pptx, openpyxl, pandas, matplotlib가 설치되어 있다.
11) Coding 과제는 tests를 수정하지 말고 소스만 고친 뒤 `run_pytest`로 검증한다.
12) 요구 산출물이 실제로 존재하고 `inspect_pptx`/테스트 등 검증 결과에 치명적 경고가 없는지 확인한 후에만 완료라고 보고한다.

네이티브 function calling이 작동하지 않을 때만 한 번에 하나씩 정확히 `TOOL_CALL {"name":"read_text","arguments":{"path":"README.md"}}` 형태를 출력한다. 러너가 TOOL_RESULT를 돌려주면 계속 작업한다. 최종 응답은 짧은 완료사항/검증결과만 쓴다.'''


def con():
    OUT.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB);c.execute('PRAGMA journal_mode=WAL')
    c.execute('''CREATE TABLE IF NOT EXISTS models(slug TEXT PRIMARY KEY,display_name TEXT,file_gib REAL,model_key TEXT,note TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS runs(model_slug TEXT,task_id TEXT,role TEXT,status TEXT,final_text TEXT,latency_s REAL,peak_vram_mib REAL,tool_calls INTEGER,tool_success INTEGER,error TEXT,workspace TEXT,PRIMARY KEY(model_slug,task_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS scores(model_slug TEXT,task_id TEXT,role TEXT,hard_score REAL,judge_score REAL,total_score REAL,reason TEXT,artifact_text TEXT,PRIMARY KEY(model_slug,task_id))''')
    c.commit();return c


def find_selected(allmodels,pattern):
    p=pattern.lower();exact=[m for m in allmodels if m.display_name.lower()==p]
    if exact:return exact[0]
    fuzzy=[m for m in allmodels if p in m.display_name.lower() or m.display_name.lower() in p]
    return fuzzy[0] if len(fuzzy)==1 else None


def resolve_run_model(allmodels, pattern):
    """Resolve --model-contains deterministically: exact display-name match wins.
    Only fall back to substring matching when there is no exact match.
    Returns (model_or_none, candidate_list).
    """
    p=str(pattern or '').strip().lower()
    exact=[m for m in allmodels if m.display_name.lower()==p]
    if len(exact)==1:
        return exact[0], exact
    fuzzy=[m for m in allmodels if p in m.display_name.lower()]
    if len(fuzzy)==1:
        return fuzzy[0], fuzzy
    return None, fuzzy


def _tool_fail_text(out, limit=1200):
    """Human-readable console diagnostic only; does not change tool results sent to the model."""
    raw=str((out or {}).get('error') or (out or {}).get('output') or '').strip()
    if not raw and (out or {}).get('returncode') is not None:
        raw=f"returncode={(out or {}).get('returncode')}"
    if len(raw)>limit:
        raw=raw[-limit:]
    return raw.replace('\r','').strip()

def _clip_context_text(text, limit, keep_tail=False):
    text=str(text or '')
    if len(text)<=limit:return text
    if keep_tail:
        head=max(200,limit//3);tail=max(200,limit-head-80)
        return text[:head]+'\n...[context clipped]...\n'+text[-tail:]
    return text[:max(200,limit-80)]+'\n...[context clipped; re-read the file/tool if needed]'


def _tool_context(out):
    """Bound what is fed back to the model; transcript keeps the full tool result."""
    raw=json.dumps(out,ensure_ascii=False)
    lim=int(CFG.get('tool_context_max_chars',9000))
    return _clip_context_text(raw,lim,keep_tail=not bool((out or {}).get('ok')))


def _message_size(m):
    n=len(str(m.get('content') or ''))
    try:n+=len(json.dumps(m.get('tool_calls') or [],ensure_ascii=False))
    except Exception:pass
    return n


def _compact_messages(messages):
    """Deterministically bound long tool histories so 16K context is not exceeded.

    Full results remain in _transcript.json. Old tool payloads/arguments are compacted,
    and the model is explicitly told to re-read workspace files when an omitted detail
    is needed. The current task/system prompt and the newest interaction stay intact.
    """
    budget=int(CFG.get('agent_history_char_budget',22000))
    out=copy.deepcopy(messages)
    if sum(_message_size(m) for m in out)<=budget:return out
    # Keep system + initial user untouched; compact old rounds first.
    last_start=max(2,len(out)-4)
    for i,m in enumerate(out):
        if i<2 or i>=last_start:continue
        role=m.get('role')
        if role=='tool':
            m['content']=_clip_context_text(m.get('content',''),900,keep_tail=True)
        elif role=='user' and str(m.get('content','')).startswith('TOOL_RESULT'):
            m['content']=_clip_context_text(m.get('content',''),900,keep_tail=True)
        elif role=='assistant':
            m['content']=_clip_context_text(m.get('content',''),900)
            for call in m.get('tool_calls') or []:
                fn=call.get('function') or {}
                arg=fn.get('arguments')
                if len(str(arg or ''))>900:fn['arguments']='{"_history_compacted":true}'
    # Cap recent payloads too, but keep enough for immediate repair work.
    for i,m in enumerate(out):
        if i<2:continue
        if m.get('role')=='tool':m['content']=_clip_context_text(m.get('content',''),6000,keep_tail=True)
        elif m.get('role')=='user' and str(m.get('content','')).startswith('TOOL_RESULT'):
            m['content']=_clip_context_text(m.get('content',''),6000,keep_tail=True)
        for call in m.get('tool_calls') or []:
            fn=call.get('function') or {};arg=fn.get('arguments')
            if len(str(arg or ''))>6000:fn['arguments']=_clip_context_text(arg,6000)
    # If still over budget, progressively shrink the oldest non-base messages.
    target=max(12000,budget)
    for i in range(2,max(2,len(out)-2)):
        if sum(_message_size(m) for m in out)<=target:break
        m=out[i]
        m['content']=_clip_context_text(m.get('content',''),350,keep_tail=True)
        for call in m.get('tool_calls') or []:
            fn=call.get('function') or {}
            if fn.get('arguments'):fn['arguments']='{"_history_compacted":true}'
    return out


def doctor():
    print(f'v{VERSION} workbench doctor')
    print('model_root =',CFG['model_root'])
    print('context =',CFG['context_length'],'max step tokens =',CFG['max_tokens_per_step'],'judge tokens =',CFG['judge_max_tokens'])
    try:start_server(CFG);print('LM Studio API: OK')
    except Exception as e:print('LM Studio API: FAIL',e)
    ms=scan_models(CFG);print('GGUF groups =',len(ms));ok=0
    for x in SELECTED:
        m=find_selected(ms,x['display_name'])
        print('[OK] ' if m else '[MISS] ',x['display_name'],f'({m.total_gib:.2f} GiB)' if m else '')
        ok+=bool(m)
    print(f'selected found = {ok}/{len(SELECTED)}')
    print('tasks =',len(TASKS),'(',', '.join(f"{r}:{sum(t['role']==r for t in TASKS)}" for r in ['Research','Coding','Data','Writer','PPT','Critic']),')')


def preflight():
    import hashlib
    print(f'v{VERSION} FINAL PREFLIGHT')
    # 1) Local deterministic renderer/grader/tool regression suite.
    selftest()
    # 2) Package integrity: task fixtures must be byte-identical to the shipped manifest.
    manifest=load_json(HERE/'fixture_sha256.json');bad=[]
    for rel,expected in manifest.items():
        fp=HERE/rel
        if not fp.exists():bad.append(f'{rel}: missing');continue
        got=hashlib.sha256(fp.read_bytes()).hexdigest()
        if got.lower()!=str(expected).lower():bad.append(f'{rel}: sha256 mismatch')
    if bad:
        for x in bad[:20]:print('[FIXTURE FAIL]',x)
        raise SystemExit(f'PREFLIGHT FAILED: fixture integrity {len(bad)} file(s)')
    print(f'[PASS] fixture integrity {len(manifest)}/{len(manifest)}')
    # 3) LM Studio authenticated HTTP path and all selected models.
    start_server(CFG);print('[PASS] LM Studio API/auth')
    ms=scan_models(CFG);missing=[]
    for x in SELECTED:
        if not find_selected(ms,x['display_name']):missing.append(x['display_name'])
    if missing:
        for x in missing:print('[MODEL MISS]',x)
        raise SystemExit(f'PREFLIGHT FAILED: selected models {len(SELECTED)-len(missing)}/{len(SELECTED)}')
    print(f'[PASS] selected models {len(SELECTED)}/{len(SELECTED)}')
    print(f'[PASS] tasks {len(TASKS)} / roles '+', '.join(f"{r}:{sum(t['role']==r for t in TASKS)}" for r in ['Research','Coding','Data','Writer','PPT','Critic']))
    print('PREFLIGHT PASS')

def selftest():
    print(f'v{VERSION} infrastructure selftest')
    root=HERE/'_selftest'
    if root.exists():shutil.rmtree(root)
    shutil.copytree(FIXTURES/'P02',root)
    checks=[]
    def chk(label,cond,detail=''):
        checks.append(bool(cond));print(('[PASS] ' if cond else '[FAIL] ')+label+(f' :: {detail}' if detail else ''))

    r=execute_tool('read_excel',{'file_path':'/workspace/investment_case.xlsx'},root,30)
    chk('xlsx alias + workspace path normalization',r.get('ok') and bool(r.get('sheets')),str(r)[:300])

    r=execute_tool('read_text',{'file_path':'/root/workspace/brief.md'},root,30)
    chk('file_path alias + relative sandbox',r.get('ok') and 'content' in r,str(r)[:300])

    r=execute_tool('write_text',{'path':'bad.pptx','content':'not a pptx'},root,30)
    chk('binary write_text rejection',not r.get('ok') and 'binary' in r.get('error','').lower(),str(r))

    good_slides=[
        {'title':'AI 설비 투자심의','subtitle':'투자비 420백만원 / 4개년 cash flow','layout':'cover','takeaway':'원자료 기준 회수기간과 리스크를 검증해 조건부 투자 여부를 판단한다.'},
        {'title':'연도별 Cash Flow','takeaway':'초기 -420 이후 4개년 유입으로 투자비를 회수한다.','bullets':['단순 매출이 아니라 제공된 cash flow 기준이다.','Year 0 투자비를 누적 계산에 포함한다.'],
         'chart':{'type':'column','title':'Cash Flow (백만원)','categories':['Y0','Y1','Y2','Y3','Y4'],'series':[{'name':'Cash Flow','values':[-420,105,125,145,155]}]}},
        {'title':'누적 Cash Flow와 Payback','takeaway':'Year 3 -45에서 Year 4 +110으로 전환되어 보간 회수기간은 약 3.29년이다.','bullets':['Payback 3.29년 = 3 + 45/155','IRR은 원자료에 없으므로 산정하지 않는다.'],
         'chart':{'type':'line','title':'Cumulative Cash Flow','categories':['Y0','Y1','Y2','Y3','Y4'],'series':[{'name':'Cumulative','values':[-420,-315,-190,-45,110]}]}},
        {'title':'리스크 우선순위','takeaway':'3개 리스크를 확률·영향과 함께 관리하고 확대 전 완화조치를 게이트로 둔다.',
         'table':{'headers':['리스크','확률','영향','완화책'],'rows':[[{'value':'파일럿 일반화 실패','bold':True}, {'value':'중','align':'center','tone':'medium'}, {'value':'높음','align':'center','tone':'high'}, '추가 라인 검증 후 확대'],['교육 지연','중','중','교육 완료율을 도입 게이트로 관리'],['센서 추가비','낮음','중','예산 contingency 반영']] }},
        {'title':'파일럿 일반화 검증 조건','takeaway':'확대 전에 대표 라인 추가 검증으로 일반화 실패 가능성을 낮춘다.','bullets':['파일럿 외 대표 라인에서 동일 KPI 방향성을 재검증한다.','성능 차이가 기준을 넘으면 확대 범위를 단계적으로 제한한다.','검증 결과를 투자 집행 게이트와 연결한다.']},
        {'title':'투자 판단 핵심 지표','takeaway':'회수기간 3.29년과 4년 누적 +110백만원을 기본 경제성 근거로 사용한다.','kpis':[{'label':'투자비','value':'420백만원','detail':'Year 0 cash flow'},{'label':'Payback','value':'3.29년','detail':'누적 cash flow 보간'},{'label':'Y4 누적','value':'+110백만원','detail':'원자료 기준'}],
         'bullets':['교육 일정과 센서 추가비는 실행 리스크로 별도 관리한다.']},
        {'title':'최종 투자 권고','layout':'decision','takeaway':'경제성은 확보되지만 실행 리스크를 통제하는 조건부 승인이 적절하다.','callout':'조건부 승인 권고',
         'bullets':['조건 1: 파일럿 일반화 추가 검증 통과','조건 2: 교육 완료 일정과 책임자 확정','조건 3: 센서 추가비 예산 한도 사전 승인']},
    ]
    r=execute_tool('create_pptx',{'path':'investment_committee.pptx','slides':good_slides},root,30)
    chk('professional create_pptx direct slides',r.get('ok') and r.get('slide_count')==7 and r.get('charts')>=2 and r.get('tables')>=1,str(r)[:500])
    loose="{slides: [{'title':'fallback one','takeaway':'message','bullets':['ok'],}, {'title':'fallback two','bullets':['content content content content content']},],}"
    (root/'loose_spec.json').write_text(loose,encoding='utf-8')
    rr=execute_tool('create_pptx',{'path':'fallback.pptx','spec_path':'loose_spec.json'},root,30)
    chk('lenient spec_path syntax fallback',rr.get('ok') and rr.get('slide_count')==2,str(rr)[:300])
    r=execute_tool('inspect_pptx',{'path':'investment_committee.pptx'},root,30)
    rich=bool(r.get('slides') and r['slides'][1].get('charts') and r['slides'][3].get('tables'))
    chk('rich PPT inspection exposes chart/table data without dict leak',r.get('ok') and rich and not r.get('quality',{}).get('empty_tables') and not r.get('quality',{}).get('dict_leaks'),str(r)[:500])
    p02=next(t for t in TASKS if t['id']=='P02')
    hard,reason,artifact=grade_task(p02,root,FIXTURES/'P02')
    chk('P02 good deck reaches high deterministic score',hard>=95,f'hard={hard}; {reason}')
    chk('P02 good deck judge cap remains high',judge_score_cap(p02,reason,artifact)>=95,f'cap={judge_score_cap(p02,reason,artifact)}')

    # A structurally valid but content-poor deck must not receive a 90+ hard score or an unrestricted Judge.
    bad_slides=[
        {'title':'투자심의위원회용 현금흐름 분석','layout':'cover','subtitle':'누적 현금흐름 및 리스크 평가'},
        {'title':'연도별 현금흐름','chart':{'type':'column','categories':['Year 0','Year 1','Year 2','Year 3','Year 4'],'series':[{'name':'Cash Flow', 'values':[-420,105,125,145,155]}]}},
        {'title':'누적 현금흐름','chart':{'type':'line','categories':['Year 0','Year 1','Year 2','Year 3','Year 4'],'series':[{'name':'Cumulative', 'values':[-420,-315,-190,-45,110]}]}},
        {'title':'Payback Period','bullets':['투자비 회수 시점: 3.2년']},
        {'title':'리스크 평가','table':{'headers':['리스크','확률','영향력'],'rows':[['','',''],['','',''],['','','']]}},
        {'title':'리스크 완화책','bullets':['파일럿 일반화 실패 방지','교육 지연 줄이기','센서 추가비 관리']},
        {'title':'결론','bullets':['리스크는 관리 가능한 수준','투자는 안정적인 현금흐름을 제공합니다.']},
    ]
    br=execute_tool('create_pptx',{'path':'bad_quality.pptx','slides':bad_slides},root,30)
    import copy
    badtask=copy.deepcopy(p02);badtask['grader']['file']='bad_quality.pptx'
    bh,breason,bartifact=grade_task(badtask,root,FIXTURES/'P02');bcap=judge_score_cap(badtask,breason,bartifact)
    chk('bad P02 deck is penalized by objective/quality grader',br.get('ok') and bh<80,f'hard={bh}; cap={bcap}; {breason}')
    chk('bad P02 deck Judge is objectively capped',bcap<=65,f'cap={bcap}')

    # Regression for the exact class of v7.1.7 renderer failure: dict/object text must be detected and blocked.
    leak_slides=[
        {'title':'Leak test','layout':'cover','takeaway':'renderer regression'},
        {'title':'Risk table','takeaway':'visible object repr must never pass QA','table':{'headers':['risk','prob','impact'],'rows':[["{'value': '파일럿 일반화 실패'}","{'value': '중'}","{'value': '높음'}"]]}},
    ]
    lr=execute_tool('create_pptx',{'path':'dict_leak.pptx','slides':leak_slides},root,30)
    li=execute_tool('inspect_pptx',{'path':'dict_leak.pptx'},root,30)
    chk('dict/object literal leak is detected',lr.get('ok') and bool(li.get('quality',{}).get('dict_leaks')),str(li.get('quality',{}))[:400])
    ready,problems=_deliverables_ready({'role':'PPT','deliverables':['dict_leak.pptx']},root)
    chk('finalization gate blocks dict/object literal leak',not ready and any('dict' in x.lower() or 'object' in x.lower() for x in problems),str(problems))


    # The other two PPT tasks must also be solvable with the same renderer/grader.
    p01root=HERE/'_selftest_p01'
    if p01root.exists():shutil.rmtree(p01root)
    shutil.copytree(FIXTURES/'P01',p01root)
    p01slides=[
        {'title':'공장 AI 성과 및 확대 검토','layout':'cover','subtitle':'2024~2026 KPI / 2026은 파일럿 라인','takeaway':'파일럿 성과를 확인하고 전사 확대의 조건을 경영진 관점에서 판단한다.'},
        {'title':'핵심 성과 요약','takeaway':'불량률은 5.2% → 4.8% → 3.1%로 개선됐지만 2026은 파일럿 라인 기준이다.','kpis':[{'label':'2024 불량률','value':'5.2%'},{'label':'2025 불량률','value':'4.8%'},{'label':'2026 파일럿','value':'3.1%'},{'label':'2026 OEE','value':'81%'}], 'bullets':['2026 결과를 전체 공장 실적으로 일반화하지 않는다.']},
        {'title':'불량률 추이','takeaway':'파일럿에서 개선 방향은 분명하지만 범위 차이를 감안해 해석해야 한다.','chart':{'type':'line','categories':['2024 전체공장','2025 전체공장','2026 파일럿 라인'],'series':[{'name':'Defect rate','values':[0.052,0.048,0.031]}]}},
        {'title':'생산성과 OEE','takeaway':'OEE는 71% → 74% → 81%로 상승했으며 2026은 파일럿 라인 성과다.','table':{'headers':['연도','범위','생산량','불량률','OEE'],'rows':[['2024','전체공장','120000','5.2%','71%'],['2025','전체공장','128000','4.8%','74%'],['2026','파일럿 라인','35000','3.1%','81%']]}},
        {'title':'파일럿 범위 해석','takeaway':'2026 3.1%는 파일럿 라인 1개 성과이므로 전사 효과로 단정할 수 없다.','bullets':['추가 라인에서 품질·OEE 재현성을 확인한다.','제품 믹스와 설비 차이에 따른 성과 편차를 검증한다.','확대 전 비교 가능한 기준선을 확정한다.']},
        {'title':'확대 시 기대효과','takeaway':'품질과 OEE 개선 방향은 확대 검토 가치가 있으나 재현성 검증이 선행돼야 한다.','bullets':['불량률 개선이 유지되면 품질비용 절감 가능성이 있다.','OEE 개선은 가동효율과 생산 여력에 기여할 수 있다.','효과 규모는 추가 파일럿 데이터로 확정한다.']},
        {'title':'확대 리스크와 조건','takeaway':'확대 전 데이터 범위·운영 표준·현장 수용성을 게이트로 관리한다.','table':{'headers':['리스크','조건'],'rows':[['파일럿 일반화','추가 라인 재현성 검증'],['운영 표준 편차','표준 작업/데이터 수집 기준 확정'],['현장 수용성','교육 및 책임자 지정']]}},
        {'title':'경영진 권고','layout':'decision','takeaway':'성과 방향은 긍정적이므로 추가 검증을 전제로 단계적 확대를 권고한다.','callout':'조건부 단계 확대 권고','bullets':['조건: 2개 이상 추가 라인에서 성과 재현','조건: KPI 정의와 데이터 수집 표준화','리스크: 2026 파일럿 수치의 과대 일반화 방지']},
    ]
    execute_tool('create_pptx',{'path':'factory_ai_review.pptx','slides':p01slides},p01root,30)
    p01=next(t for t in TASKS if t['id']=='P01');h1,r1,_=grade_task(p01,p01root,FIXTURES/'P01')
    chk('P01 hard grader remains solvable at high quality',h1>=95,f'hard={h1}; {r1}')

    p03root=HERE/'_selftest_p03'
    if p03root.exists():shutil.rmtree(p03root)
    shutil.copytree(FIXTURES/'P03',p03root)
    p03slides=[
        {'title':'설비 과열 사고 리뷰','layout':'cover','subtitle':'사건 흐름 / 직접 트리거 / RCA 불확실성 / 조치계획','takeaway':'보호정지까지의 사실과 근본원인 가설을 분리해 후속조치를 결정한다.'},
        {'title':'사건 타임라인','takeaway':'14:02 고온 경고 이후 14:07 보호정지, 14:16 분진 확인, 14:31 재가동 순으로 진행됐다.','timeline':[{'time':'14:02','text':'고온 경고'},{'time':'14:04','text':'91.1C'},{'time':'14:07','text':'보호정지'},{'time':'14:16','text':'냉각 흡입구 분진 확인'},{'time':'14:31','text':'분진 제거 후 재가동'}]},
        {'title':'직접 트리거','takeaway':'직접 트리거는 14:07 보호정지이며 분진 발견은 이후 확인된 관찰 사실이다.','bullets':['고온 경고와 91.1C 온도 상승이 선행했다.','14:07 보호정지가 설비를 안전 상태로 전환했다.','분진은 14:16 흡입구에서 확인됐다.']},
        {'title':'근본원인 상태','takeaway':'분진은 유력 가설이지만 진동 데이터 누락 때문에 근본원인은 미확정이며 추가 검증이 필요하다.','bullets':['분진 제거 후 재가동은 인과 가능성을 높이지만 확정 증거는 아니다.','진동 데이터 누락 복구 후 RCA를 재검증한다.','분진을 근본원인으로 단정하지 않는다.']},
        {'title':'조치 계획','takeaway':'즉시 조치와 1~2주 내 RCA 보강 조치를 owner/due로 관리한다.','table':{'headers':['action','owner','due'],'rows':[['흡입구 청소주기 4주 준수','설비팀','즉시'],['진동센서 수집 누락 복구','자동화팀','2주'],['과열 RCA 재검증','품질팀','1주']]}},
        {'title':'공장장 의사결정 요청','layout':'decision','takeaway':'운전 재개와 별개로 RCA 검증을 완료할 때까지 재발방지 조치를 추적해야 한다.','callout':'RCA 재검증 완료까지 조치 추적','bullets':['설비팀: 청소주기 즉시 준수','자동화팀: 진동 데이터 2주 내 복구','품질팀: 1주 내 과열 RCA 재검증']},
    ]
    execute_tool('create_pptx',{'path':'incident_review.pptx','slides':p03slides},p03root,30)
    p03=next(t for t in TASKS if t['id']=='P03');h3,r3,_=grade_task(p03,p03root,FIXTURES/'P03')
    chk('P03 hard grader remains solvable at high quality',h3>=95,f'hard={h3}; {r3}')

    p=root/'edit.txt';p.write_text('alpha beta',encoding='utf-8')
    r=execute_tool('edit_file',{'path':'edit.txt','old_text':'beta','new_text':'gamma'},root,30)
    chk('edit_file',r.get('ok') and p.read_text(encoding='utf-8')=='alpha gamma',str(r))

    dummy={'grader':{'type':'pptx'}}
    ok,_=judge_eligible(dummy,0,'pptx 없음','')
    chk('judge gate rejects missing PPTX',not ok)

    class _M:
        def __init__(self,name): self.display_name=name
    mm=[_M('DeepSeek-R1-0528-Qwen3-8B-Q6_K'),_M('Qwen3-8B-Q6_K')]
    picked,cands=resolve_run_model(mm,'Qwen3-8B-Q6_K')
    chk('exact model match beats substring collision',picked is mm[1] and len(cands)==1)

    # v7.2.1 regression: running pytest creates __pycache__ and must NOT count as test tampering.
    tamproot=HERE/'_selftest_tamper'
    if tamproot.exists():shutil.rmtree(tamproot)
    shutil.copytree(FIXTURES/'C01'/'tests',tamproot)
    h0=hash_tree(FIXTURES/'C01'/'tests');h1=hash_tree(tamproot)
    (tamproot/'__pycache__').mkdir(exist_ok=True);(tamproot/'__pycache__'/'noise.pyc').write_bytes(b'cache')
    (tamproot/'.pytest_cache').mkdir(exist_ok=True);(tamproot/'.pytest_cache'/'nodeids').write_text('cache',encoding='utf-8')
    hcache=hash_tree(tamproot)
    chk('pytest cache files do not trigger protected-test tamper',h0==h1==hcache)
    tfile=next(x for x in tamproot.glob('*.py'))
    tfile.write_text(tfile.read_text(encoding='utf-8')+'\n# semantic change\n',encoding='utf-8')
    chk('real protected-test edits are still detected',hash_tree(tamproot)!=h0)

    # v7.2.1 regression: Windows cp949 console/subprocess must not crash on U+FFFD/Korean.
    utfroot=HERE/'_selftest_utf8';utfroot.mkdir(exist_ok=True)
    (utfroot/'utf8_probe.py').write_text("print('\\ufffd 한글 UTF8 probe')\n",encoding='utf-8')
    ur=execute_tool('run_python',{'path':'utf8_probe.py'},utfroot,30)
    chk('run_python forces UTF-8 child I/O',ur.get('ok') and 'UTF8 probe' in str(ur.get('output','')),str(ur)[:300])

    # v7.2.1 regression: repeated large tool results must be compacted before 16K requests.
    huge=[{'role':'system','content':'system'},{'role':'user','content':'task'}]
    for i in range(10):
        huge.append({'role':'assistant','content':'working','tool_calls':[{'id':f'c{i}','type':'function','function':{'name':'read_text','arguments':json.dumps({'path':'x','blob':'Z'*6000})}}]})
        huge.append({'role':'tool','tool_call_id':f'c{i}','content':'X'*9000})
    compact=_compact_messages(huge);cs=sum(_message_size(m) for m in compact)
    chk('agent history compaction stays within configured budget',cs<=int(CFG.get('agent_history_char_budget',22000))+1500,f'chars={cs}')

    # SQL regression: runs has an `error` column, so status comparisons must use parameters/single-quoted values.
    qc=sqlite3.connect(':memory:');qc.execute('CREATE TABLE runs(status TEXT,error TEXT)');qc.execute('INSERT INTO runs VALUES(?,?)',('ERROR','boom'))
    ec=qc.execute('SELECT COUNT(*) FROM runs WHERE status=?',('ERROR',)).fetchone()[0];qc.close()
    chk('ERROR status counting is not confused with error column',ec==1)

    shutil.rmtree(root,ignore_errors=True)
    shutil.rmtree(p01root,ignore_errors=True)
    shutil.rmtree(p03root,ignore_errors=True)
    shutil.rmtree(tamproot,ignore_errors=True)
    shutil.rmtree(utfroot,ignore_errors=True)
    if not all(checks):raise SystemExit('SELFTEST FAILED')
    print('SELFTEST PASS')


def upsert_model(c,m,note=''):
    c.execute('INSERT OR REPLACE INTO models(slug,display_name,file_gib,model_key,note) VALUES(?,?,?,?,?)',(m.slug,m.display_name,m.total_gib,m.model_key,note));c.commit()


def _balanced_json_objects(text):
    objs=[]
    for start,ch0 in enumerate(text or ''):
        if ch0!='{':continue
        depth=0;ins=False;esc=False
        for i in range(start,len(text)):
            ch=text[i]
            if ins:
                if esc:esc=False
                elif ch=='\\':esc=True
                elif ch=='"':ins=False
                continue
            if ch=='"':ins=True
            elif ch=='{':depth+=1
            elif ch=='}':
                depth-=1
                if depth==0:
                    raw=text[start:i+1]
                    try:objs.append(json.loads(raw))
                    except Exception:pass
                    break
    return objs


def parse_text_tool_call(text):
    if not text or 'TOOL_CALL' not in text:return None
    tail=text.split('TOOL_CALL',1)[1]
    for obj in _balanced_json_objects(tail):
        if isinstance(obj,dict) and obj.get('name'):return obj
    return None


def _deliverables_ready(task, ws):
    """Physical validity + only severe generic quality failures.

    Semantic correctness is graded later. This gate merely prevents a model from declaring
    success with a corrupt, visibly broken, mostly empty, or object-leaking PPTX.
    """
    problems=[]
    for rel in task.get('deliverables',[]):
        p=ws/rel
        if not p.exists() or not p.is_file():
            problems.append(f'{rel}: missing');continue
        try:
            if p.stat().st_size <= 0:problems.append(f'{rel}: empty');continue
            suf=p.suffix.lower()
            if suf=='.pptx':
                try:
                    with zipfile.ZipFile(p,'r') as z:names=set(z.namelist())
                    if '[Content_Types].xml' not in names or 'ppt/presentation.xml' not in names:
                        problems.append(f'{rel}: invalid pptx structure');continue
                    info=inspect_pptx_structure(p);q=info.get('quality',{})
                    if q.get('dict_leaks'):problems.append(f'{rel}: visible object/dict text leak')
                    if q.get('empty_tables'):problems.append(f'{rel}: empty/incomplete table')
                    if q.get('sparse_ratio',0)>0.34:problems.append(f'{rel}: too many sparse slides ({q.get("sparse_ratio")})')
                    if len(q.get('text_overlaps',[]))>=2:problems.append(f'{rel}: multiple text overlaps')
                    if len(q.get('overflow_risks',[]))>=3:problems.append(f'{rel}: multiple text overflow risks')
                    if q.get('min_font_pt') is not None and q.get('min_font_pt')<9:problems.append(f'{rel}: font below 9pt')
                    if float(q.get('design_score',100) or 0)<45:problems.append(f'{rel}: severe layout quality ({q.get("design_score")}/100)')
                    miss=len(q.get('missing_takeaway_slides',[]));den=max(1,info.get('slide_count',1)-1)
                    if task.get('role')=='PPT' and miss/den>0.50:problems.append(f'{rel}: most content slides lack takeaway')
                except Exception as e:problems.append(f'{rel}: invalid pptx ({type(e).__name__}: {e})')
            elif suf=='.json':
                try:json.loads(p.read_text(encoding='utf-8-sig'))
                except Exception as e:problems.append(f'{rel}: invalid json ({type(e).__name__})')
            elif suf=='.png':
                try:
                    from PIL import Image
                    with Image.open(p) as im:im.verify()
                except Exception as e:problems.append(f'{rel}: invalid png ({type(e).__name__})')
            elif suf=='.xlsx':
                try:
                    from openpyxl import load_workbook
                    wb=load_workbook(p,read_only=True,data_only=False);wb.close()
                except Exception as e:problems.append(f'{rel}: invalid xlsx ({type(e).__name__})')
        except Exception as e:problems.append(f'{rel}: validation error ({type(e).__name__})')
    return (not problems),problems

def run_agent_task(m,task,ws):
    user=task['prompt']+'\n\n현재 workspace에는 이 과제용 파일만 있다. 먼저 list_files로 실제 파일명을 확인하고 위 도구 규칙을 지켜라.'
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':user}]
    transcript=[];total_latency=0.;tc=ts=0;final='';error='';mon=GPUMonitor(CFG);mon.start()
    try:
        for step in range(1,int(CFG['max_agent_steps'])+1):
            res=chat_messages(CFG,_compact_messages(messages),TOOL_SCHEMAS);total_latency+=res['latency'];msg=res['message'];calls=msg.get('tool_calls') or []
            transcript.append({'step':step,'assistant':msg,'finish_reason':res.get('finish_reason')})
            if calls:
                messages.append({'role':'assistant','content':msg.get('content') or '', 'tool_calls':calls})
                for call in calls:
                    tc+=1;fn=call.get('function') or {};name=fn.get('name','');args=fn.get('arguments',{})
                    out=execute_tool(name,args,ws,int(CFG['tool_timeout_sec']));ts+=int(bool(out.get('ok')))
                    transcript.append({'tool_mode':'native','tool':name,'arguments':args,'result':out})
                    if not out.get('ok'):
                        detail=_tool_fail_text(out)
                        if '\n' in detail:
                            print(f"        TOOL FAIL {name}:",flush=True)
                            for line in detail.splitlines()[-12:]: print(f"          {line}",flush=True)
                        else:
                            print(f"        TOOL FAIL {name}: {detail}",flush=True)
                    messages.append({'role':'tool','tool_call_id':call.get('id',''), 'content':_tool_context(out)})
                continue
            candidate=(msg.get('content') or '').strip() or (msg.get('reasoning_content') or msg.get('reasoning') or '').strip()
            text_call=parse_text_tool_call(candidate)
            if text_call:
                tc+=1;name=str(text_call.get('name',''));args=text_call.get('arguments') or {}
                out=execute_tool(name,args,ws,int(CFG['tool_timeout_sec']));ts+=int(bool(out.get('ok')))
                transcript.append({'tool_mode':'text-fallback','tool':name,'arguments':args,'result':out})
                if not out.get('ok'):
                    detail=_tool_fail_text(out)
                    if '\n' in detail:
                        print(f"        TOOL FAIL {name}:",flush=True)
                        for line in detail.splitlines()[-12:]: print(f"          {line}",flush=True)
                    else:
                        print(f"        TOOL FAIL {name}: {detail}",flush=True)
                messages.append({'role':'assistant','content':candidate})
                messages.append({'role':'user','content':'TOOL_RESULT '+_tool_context(out)+'\n계속 작업하라. 실패했다면 list_files와 정확한 상대경로/도구 이름으로 복구하라.'})
                continue
            ready,problems=_deliverables_ready(task,ws)
            if task.get('deliverables') and not ready:
                transcript.append({'step':step,'finalization_gate':'blocked','problems':problems,'candidate':candidate})
                print('        FINAL BLOCKED: '+ '; '.join(problems),flush=True)
                messages.append({'role':'assistant','content':candidate})
                messages.append({'role':'user','content':
                    '작업 종료 불가. 필수 산출물이 실제로 없거나 손상되어 있다: '+ '; '.join(problems)+
                    '. 설명으로 끝내지 말고 남은 도구를 사용해 실제 산출물을 생성/수정하고, 필요하면 실행 후 검수하라. '
                    'PPTX는 write_text로 직접 만들지 말고 create_pptx에 slides 배열을 직접 전달해 생성한 뒤 inspect_pptx로 확인하라. spec_path는 fallback이며 필요할 때만 run_python을 보조적으로 사용하라.'})
                continue
            final=candidate
            break
        else:
            ready,problems=_deliverables_ready(task,ws)
            if ready:
                final='max_agent_steps reached after valid deliverables were created'
            else:
                error='max_agent_steps reached; missing/invalid deliverables: '+ '; '.join(problems)
    except Exception as e:error=f'{type(e).__name__}: {e}'
    peak=mon.stop();(ws/'_transcript.json').write_text(json.dumps(transcript,ensure_ascii=False,indent=2),encoding='utf-8')
    return final,error,total_latency,peak,tc,ts


def run_one(c,m,tasks,retry_errors=False):
    ok,note=ensure_imported(m,CFG);upsert_model(c,m,note)
    if not ok:print('IMPORT FAILED',note);return
    ok,note=load_model(m,CFG)
    if not ok:print('LOAD FAILED',note);return
    print('LOAD OK',note)
    try:
        for i,task in enumerate(tasks,1):
            row=c.execute('SELECT status FROM runs WHERE model_slug=? AND task_id=?',(m.slug,task['id'])).fetchone()
            if row and row[0]=='DONE':print(f"  [{i}/{len(tasks)}] {task['id']} already DONE -> skip");continue
            if row and row[0]=='ERROR' and not retry_errors:print(f"  [{i}/{len(tasks)}] {task['id']} ERROR stored -> skip (--retry-errors to retry)");continue
            print(f"  [{i}/{len(tasks)}] {task['id']} {task['role']} {task['title']}",flush=True)
            ws=reset_workspace(FIXTURES,RUNS,m.slug,task['id']);final,err,lat,peak,tc,ts=run_agent_task(m,task,ws)
            status='ERROR' if err else 'DONE'
            c.execute('INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(m.slug,task['id'],task['role'],status,final,lat,peak,tc,ts,err,str(ws)));c.commit()
            if not err:
                hard,reason,artifact=grade_task(task,ws,FIXTURES/task['id'])
                hw=float(task.get('hard_weight',1))
                judge_score=None;total=hard if hw>=.999 else None
                if hw<.999:
                    eligible,why=judge_eligible(task,hard,reason,artifact)
                    if not eligible:
                        judge_score=0.0;total=0.0;reason=reason+' | JUDGE SKIPPED: INVALID ARTIFACT ('+why+')'
                c.execute('INSERT OR REPLACE INTO scores(model_slug,task_id,role,hard_score,judge_score,total_score,reason,artifact_text) VALUES(?,?,?,?,?,?,?,?)',(m.slug,task['id'],task['role'],hard,judge_score,total,reason,artifact));c.commit()
                extra=' [judge skipped invalid artifact]' if judge_score==0.0 and hw<.999 else ''
                print(f'      hard={hard} tool={ts}/{tc} peak={peak/1024:.2f}GiB{extra}')
            else:print('      ERROR',err)
    finally:unload_all(CFG)


def choose_tasks(args):
    ts=TASKS
    if getattr(args,'role',''):ts=[t for t in ts if t['role'].lower()==args.role.lower()]
    if getattr(args,'task',''):ts=[t for t in ts if t['id'].lower()==args.task.lower()]
    if getattr(args,'max_tasks',0):ts=ts[:args.max_tasks]
    return ts


def cmd_run(args):
    start_server(CFG);ms=scan_models(CFG);m,candidates=resolve_run_model(ms,args.model_contains)
    if not m:
        print('model match count=',len(candidates));[print(' ',x.display_name) for x in candidates[:30]];raise SystemExit(2)
    c=con();run_one(c,m,choose_tasks(args),args.retry_errors);write_reports(c,OUT)


def cmd_selected(args):
    start_server(CFG);ms=scan_models(CFG);c=con();tasks=choose_tasks(args)
    for i,x in enumerate(SELECTED,1):
        m=find_selected(ms,x['display_name']);print(f'\n========== MODEL {i}/{len(SELECTED)} {x["display_name"]} ==========')
        if not m:print('NOT FOUND -> skip');continue
        if m.total_gib>float(CFG['hard_file_limit_gib']):print('FILE TOO LARGE -> skip');continue
        run_one(c,m,tasks,args.retry_errors)
    write_reports(c,OUT)


def parse_json_score(text):
    for d in _balanced_json_objects(text or ''):
        if isinstance(d,dict) and 'score' in d:
            try:return max(0,min(100,float(d['score']))),str(d.get('reason',''))
            except Exception:pass
    return None,'judge JSON parse failed: '+str(text or '')[-1200:]


def _judge_once(jm,t,prompt):
    msgs=[{'role':'system','content':'엄격한 독립 업무품질 평가자다. 반드시 제공된 원자료와 실제 산출물만 사용한다. [PPT AUDIT]가 있으면 그 객관 판정을 절대 뒤집지 말고, 산출물에 없는 내용/표/차트/시각요소를 상상하지 않는다. PPT에서는 숫자 정확성이나 표 완전성을 재채점하지 말고 AUDIT을 전제로 스토리라인·의사결정 유용성·시각 계층·정보밀도 같은 주관 품질만 평가한다. 90~100은 거의 수정 없이 실제 제출 가능한 수준에만 사용한다. JSON 하나만 출력한다.'},{'role':'user','content':prompt}]
    r=chat_messages(CFG,msgs,None,max_tokens=int(CFG['judge_max_tokens']),temperature=0)
    msg=r['message'];txt=(msg.get('content') or msg.get('reasoning_content') or msg.get('reasoning') or '')
    return parse_json_score(txt)


def cmd_judge(args):
    start_server(CFG);ms=scan_models(CFG);pat=CFG['judge_model_contains'];jm=find_selected(ms,pat) or next((m for m in ms if pat.lower() in m.display_name.lower()),None)
    if not jm:raise RuntimeError('judge model not found: '+pat)
    ok,note=ensure_imported(jm,CFG)
    if not ok:raise RuntimeError(note)
    ok,note=load_model(jm,CFG)
    if not ok:raise RuntimeError(note)
    c=con();taskmap={t['id']:t for t in TASKS}
    rows=c.execute('''SELECT s.model_slug,s.task_id,s.hard_score,s.reason,s.artifact_text,m.display_name FROM scores s JOIN models m ON m.slug=s.model_slug WHERE s.total_score IS NULL ORDER BY m.display_name,s.task_id''').fetchall()
    print('pending judge =',len(rows))
    try:
        for i,(slug,tid,hard,oldreason,artifact,name) in enumerate(rows,1):
            t=taskmap[tid];rub=t['grader'].get('judge_rubric')
            if not rub:
                c.execute('UPDATE scores SET judge_score=?,total_score=? WHERE model_slug=? AND task_id=?',(hard,hard,slug,tid));c.commit();continue
            eligible,why=judge_eligible(t,hard,oldreason,artifact)
            if not eligible:
                reason=(oldreason or '')+' | JUDGE SKIPPED: INVALID ARTIFACT ('+why+')'
                c.execute('UPDATE scores SET judge_score=0,total_score=0,reason=? WHERE model_slug=? AND task_id=?',(reason,slug,tid));c.commit()
                print(f'[{i}/{len(rows)}] {name} {tid}: invalid artifact -> total 0')
                continue
            ref=build_reference_packet(FIXTURES/tid,int(CFG.get('judge_reference_max_chars',12000)))
            art=(artifact or '')[:int(CFG.get('judge_artifact_max_chars',14000))]
            prompt=f'''다음 실무 과제를 원자료와 실제 산출물에 근거해 채점하라. 모델 이름은 무시한다.\n\nTask: {t['title']}\n요구사항: {t['prompt']}\n평가기준:\n- '''+'\n- '.join(rub)+f'''\n\n[원자료/참조]\n{ref}\n\n[실제 산출물]\n{art}\n\n원자료로 확인할 수 없는 내용은 정확하다고 가정하지 마라. 실제 산출물에 없는 차트/표/텍스트를 있다고 평가하지 마라. [PPT AUDIT]가 있으면 objective/design/empty-table/dict-leak/sparse/overflow 판정을 사실로 받아들여라. PPT의 Judge 점수는 객관 정확성 점수가 아니라 스토리라인·의사결정 유용성·시각 계층·정보밀도·마무리 완성도에만 집중한다. 점수 기준: 90~100=거의 수정 없이 실제 제출 가능, 75~89=강하지만 일부 수정 필요, 60~74=내용은 있으나 실무 완성도 부족, 40~59=중요한 구성/전달 문제, 0~39=부적합. 반드시 JSON 하나만 출력: {{"score":0~100,"reason":"원자료와 산출물 비교 근거 2~4문장"}}'''
            try:js,reason=_judge_once(jm,t,prompt)
            except Exception as e:js=None;reason=str(e)
            if js is None:
                repair=prompt+'\n\n이전 출력은 JSON 파싱에 실패했다. 설명/마크다운 없이 JSON 객체 하나만 다시 출력하라.'
                try:js,reason=_judge_once(jm,t,repair)
                except Exception as e:js=None;reason=str(e)
            if js is not None:
                cap=judge_score_cap(t,oldreason,artifact);raw_js=float(js);js=min(raw_js,float(cap))
                if js < raw_js:reason=f'[objective cap {cap:.0f}; raw judge {raw_js:.1f}] '+reason
                hw=float(t.get('hard_weight',.5));total=hw*float(hard)+(1-hw)*js
                c.execute('UPDATE scores SET judge_score=?,total_score=?,reason=reason||? WHERE model_slug=? AND task_id=?',(js,total,' | JUDGE: '+reason,slug,tid));c.commit()
                print(f'[{i}/{len(rows)}] {name} {tid}: hard {hard} judge {js} cap {cap} total {total:.1f}')
            else:print(f'[{i}/{len(rows)}] {name} {tid}: judge failed {reason}')
    finally:unload_all(CFG)
    write_reports(c,OUT)



_INFRA_ERROR_MARKERS=('UnicodeEncodeError','exceed_context_size_error')

def finalcheck():
    """Fail closed unless the benchmark has a complete, internally consistent result set."""
    c=con()
    total=c.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    done=c.execute("SELECT COUNT(*) FROM runs WHERE status=?",("DONE",)).fetchone()[0]
    error=c.execute("SELECT COUNT(*) FROM runs WHERE status=?",("ERROR",)).fetchone()[0]
    scored=c.execute("SELECT COUNT(*) FROM scores WHERE total_score IS NOT NULL").fetchone()[0]
    pending=c.execute("SELECT COUNT(*) FROM scores WHERE total_score IS NULL").fetchone()[0]
    problems=[]
    expected=len(SELECTED)*len(TASKS)
    if total!=expected:problems.append(f"runs {total}/{expected}")
    if done+error!=total:problems.append(f"unresolved status rows: total={total}, DONE+ERROR={done+error}")
    if scored!=done:problems.append(f"scored DONE mismatch: scored={scored}, DONE={done}")
    if pending:problems.append(f"judge pending={pending}")
    counts={name:(n,res or 0) for name,n,res in c.execute("SELECT m.display_name, COUNT(r.task_id), SUM(CASE WHEN r.status IN ('DONE','ERROR') THEN 1 ELSE 0 END) FROM models m LEFT JOIN runs r ON r.model_slug=m.slug GROUP BY m.slug,m.display_name").fetchall()}
    for x in SELECTED:
        name=x["display_name"]; n,res=counts.get(name,(0,0))
        if n!=len(TASKS) or res!=len(TASKS):problems.append(f"{name}: tasks={n}, resolved={res}, expected={len(TASKS)}")
    if problems:
        print("FINALCHECK FAIL")
        for x in problems:print("  -",x)
        raise SystemExit(2)
    print(f"FINALCHECK PASS: runs={total}, DONE={done}, ERROR(zero)={error}, scored={scored}, judge_pending={pending}, models={len(SELECTED)}/{len(SELECTED)} complete")


def cmd_finalcheck(args):
    write_reports(con(),OUT)
    finalcheck()


def cmd_migrate_v721(args):
    """Reuse v7.2.1 work while removing only proven infrastructure-corrupted runs.

    DONE artifacts are preserved. Genuine model ERROR rows are preserved as zero-score
    outcomes. Coding DONE tasks are regraded because v7.2.1 falsely treated pytest cache
    files as test tampering. Only Unicode console crashes and context-overflow runs are
    deleted so `run-selected` will retry exactly those infrastructure failures.
    """
    src=Path(args.source).resolve(); srcdb=src/'results'/'work'/'benchmark.db'; srcruns=src/'runs'
    if not srcdb.exists():raise RuntimeError(f'v7.2.1 benchmark.db not found: {srcdb}')
    if not srcruns.exists():raise RuntimeError(f'v7.2.1 runs folder not found: {srcruns}')
    # Refuse to mix results from a different task/fixture generation.
    srcver=(src/'VERSION.txt').read_text(encoding='utf-8-sig').strip() if (src/'VERSION.txt').exists() else ''
    if srcver!='7.2.1':raise RuntimeError(f'migration source must be v7.2.1, got {srcver!r}')
    if load_json(src/'tasks.json')!=TASKS:raise RuntimeError('v7.2.1 tasks.json differs from v7.2.2; fresh run required')
    if load_json(src/'selected_models.json')!=SELECTED:raise RuntimeError('v7.2.1 selected_models.json differs; fresh run required')
    if load_json(src/'fixture_sha256.json')!=load_json(HERE/'fixture_sha256.json'):raise RuntimeError('v7.2.1 fixture manifest differs; fresh run required')
    OUT.mkdir(parents=True,exist_ok=True)
    if DB.exists() and not args.force:raise RuntimeError(f'{DB} already exists. Use --force only when you intend to replace v7.2.2 local results.')
    if DB.exists():DB.unlink()
    for ext in ('-wal','-shm'):
        q=Path(str(DB)+ext)
        if q.exists():q.unlink()
    # SQLite backup safely includes committed state even if the source used WAL mode.
    sc=sqlite3.connect(srcdb); dc=sqlite3.connect(DB)
    try:sc.backup(dc)
    finally:sc.close();dc.close()
    if RUNS.exists():shutil.rmtree(RUNS)
    shutil.copytree(srcruns,RUNS)
    c=con()
    # Update report workspace paths to the copied v7.2.2 tree.
    c.execute('UPDATE runs SET workspace=REPLACE(workspace,?,?)',(str(src),str(HERE)));c.commit()
    infra=[]
    for slug,tid,err in c.execute("SELECT model_slug,task_id,error FROM runs WHERE status='ERROR'").fetchall():
        if any(x in str(err or '') for x in _INFRA_ERROR_MARKERS):infra.append((slug,tid,str(err or '')))
    for slug,tid,_ in infra:
        c.execute('DELETE FROM scores WHERE model_slug=? AND task_id=?',(slug,tid))
        c.execute('DELETE FROM runs WHERE model_slug=? AND task_id=?',(slug,tid))
        ws=RUNS/slug/tid
        if ws.exists():shutil.rmtree(ws)
    c.commit()
    taskmap={t['id']:t for t in TASKS};regraded=0
    for slug,tid in c.execute("SELECT model_slug,task_id FROM runs WHERE status='DONE' AND role='Coding'").fetchall():
        t=taskmap.get(tid);ws=RUNS/slug/tid
        if not t or not ws.exists():continue
        hard,reason,artifact=grade_task(t,ws,FIXTURES/tid)
        c.execute('INSERT OR REPLACE INTO scores(model_slug,task_id,role,hard_score,judge_score,total_score,reason,artifact_text) VALUES(?,?,?,?,?,?,?,?)',
                  (slug,tid,t['role'],hard,None,hard,reason,artifact));regraded+=1
    c.commit()
    genuine=c.execute("SELECT COUNT(*) FROM runs WHERE status='ERROR'").fetchone()[0]
    done=c.execute("SELECT COUNT(*) FROM runs WHERE status='DONE'").fetchone()[0]
    attempted=c.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
    print(f'[MIGRATE] source={src}')
    print(f'[MIGRATE] copied runs={attempted}: DONE={done}, preserved genuine ERROR={genuine}')
    print(f'[MIGRATE] removed infrastructure-corrupted runs for retry={len(infra)}')
    for slug,tid,err in infra:print(f'  [RETRY] {slug} {tid}: {err[:120]}')
    print(f'[MIGRATE] regraded Coding DONE tasks={regraded} with cache-safe tamper detection')
    write_reports(c,OUT)


def cmd_report(args):write_reports(con(),OUT)


def main():
    ap=argparse.ArgumentParser(description=f'Local LLM Work Benchmark v{VERSION}')
    sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('doctor');p.set_defaults(fn=lambda a:doctor())
    p=sp.add_parser('selftest');p.set_defaults(fn=lambda a:selftest())
    p=sp.add_parser('preflight');p.set_defaults(fn=lambda a:preflight())
    for name,fn in [('run',cmd_run),('run-selected',cmd_selected)]:
        p=sp.add_parser(name)
        if name=='run':p.add_argument('--model-contains',required=True)
        p.add_argument('--role',default='');p.add_argument('--task',default='');p.add_argument('--max-tasks',type=int,default=0);p.add_argument('--retry-errors',action='store_true');p.set_defaults(fn=fn)
    p=sp.add_parser('judge');p.set_defaults(fn=cmd_judge)
    p=sp.add_parser('migrate-v721');p.add_argument('--source',default=r'C:\AI\Benchmark_v7_2_1');p.add_argument('--force',action='store_true');p.set_defaults(fn=cmd_migrate_v721)
    p=sp.add_parser('finalcheck');p.set_defaults(fn=cmd_finalcheck)
    p=sp.add_parser('report');p.set_defaults(fn=cmd_report)
    a=ap.parse_args();a.fn(a)

if __name__=='__main__':main()
