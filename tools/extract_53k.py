"""Extract actual original DOCX cells, preserving provenance and incomplete capacity-protection evidence."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from docx import Document
from tools.extract_golden import Reference, Golden, q
from bridge_report.engine.gates import validate, evaluate

SOURCE = next((ROOT / 'templates/reference').glob('*53K*.docx'))
OUT = ROOT / 'examples/golden/53K271+730'
REV = '53K271+730-原报告-2026.03'


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'assets').mkdir(exist_ok=True)
    ref = Reference(SOURCE)
    tables = [[[c.text.strip() for c in r.cells] for r in t.rows] for t in Document(SOURCE).tables]
    seed = json.loads((ROOT/'tools/case53-metadata.json').read_text(encoding='utf-8'))
    p = {key:seed[key] for key in ('project','overview','codes')}
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    p.update(contract_version='2.0',data_kind='reference_reproduction',bridge_id='G8511-K271+730',model_revision=REV,scenario='original',
             analysis={'software':'SAP 2000 V22（转录原报告，未重新运行）','converged':True,'axial_sign':'compression_positive',
                       'coordinate_convention':'纵桥向 X，横桥向 Y，竖向 Z','methods':{'E1':'response_spectrum','E2':'nonlinear_time_history'}},
             scope_review={'approved':True,'evidence':'orig-53K','note':'复现原报告选取范围，不代表工程审批'},
             sources={'orig-53K':{'kind':'external','title':SOURCE.name,'sha256':source_hash,'note':'原 DOCX 单元格逐项抽取，原表序号与行号见 locator'}},
             checks=[],actions=[],components=[],not_applicable=[],assets=[])
    p['overview']['description']=ref.text(62)+' '+ref.text(63)+' '+ref.text(64)
    p['overview']['pier_description']=ref.text(73)
    p['overview']['research_scope']=ref.text(77)+' 本案例按原报告复现；1#桩超强复算表有数值但缺少合同要求的复算系数与审核证据，保留为待补正。'
    p['project'].update(stake='K271+730',stake_line='设计桩号 K271+730',short_name='K271+730',spans_m=[30.3,30,30.3],span_text=ref.text(10),bridge_type=ref.text(11))
    def n(v):return float(v.replace(',','').strip())
    def tab(i):return {'header':tables[i][0],'rows':tables[i][1:]}
    p['seismic']={'intensity':'Ⅶ度','pga_g':.15,'site_class':'Ⅱ类','tg_s':.45,'category':'B类',
                  'performance_objectives':[dict(category='B类',e1_use=tables[3][3][1],e1_damage=tables[3][3][2],e2_use=tables[3][3][3],e2_damage=tables[3][3][4])],
                  'spectrum':[dict(level='E1' if i==0 else 'E2',location=r[0],site_class=r[2],Tg=n(r[3]),Ci=n(r[4]),Cs=n(r[5]),Cd=n(r[6]),A=n(r[7]),Smax=n(r[8])) for i,r in enumerate(tables[4][1:])],
                  'time_history':seed.get('seismic',{}).get('time_history',{}),'figures':{}}
    p['materials']={'description':ref.text(101).split('由于')[0],'rebar_intro':ref.text(119).split('，材料参数')[0],'old_code_conversion':True,'old_code':'JTJ 023-85','concrete_table':tab(1),'rebar_table':tab(2)}
    p['model']={'software':'SAP 2000 V22','nodes':152,'elements':133,'linear_boundary':tab(5),
                'element_modeling':'主梁、盖梁、桥墩及桩基采用空间梁单元，支座采用连接单元，沿桩身布置土弹簧模拟桩土相互作用。','foundation':{'method':'distributed_m','springs':tab(7),'notes':['原报告土层参数表与弹簧表所列 m 值存在差异，本次原样转录，须专业复核。']},
                'bearings':{'description':ref.text(203),'family':'板式橡胶支座','model_name':'YPQ / YPQF4','nonlinear_boundary':tab(8)},'figures':{}}
    p['modal']={'modes':[{'n':int(r[0]),'period_s':n(r[1]),'frequency_hz':n(r[2])} for r in tables[9][1:]],'figures':[]}
    for i in (1,2):
        p['components'] += [{'id':f'P{i}','kind':'pier','label':f'{i}#双柱墩（各验算取不利柱）','directions':['longitudinal','transverse']},
                            {'id':f'F{i}','kind':'pile','label':f'{i}#桩','parent_pier':f'P{i}','directions':['longitudinal','transverse']}]
    for i in range(4):p['components'].append({'id':f'B{i}','kind':'bearing','label':f'{i}#支座','directions':['longitudinal','transverse']})
    for i in (1,2):
        for suffix,label in [('M','抗弯'),('V','抗剪')]:p['components'].append({'id':f'C{i}{suffix}','kind':'capbeam','label':f'{i}#盖梁{label}专项','directions':['transverse']})
    mappings=[]
    def add(table,row_no,component,direction,level,kind,demand_col,capacity_col,unit,**extra):
        row=tables[table][row_no]
        caption=next((ref.text(i-1) for i,e in enumerate(ref.kids) if e.tag==q('tbl') and ref.table(i)==tables[table]),None)
        # DOCX table index + 1 is stable even when adjacent caption formatting differs.
        record=dict(id=f'{level}-{component}-{direction}-{kind}',component=component,section_label=row[1].replace(' ',''),direction=direction,level=level,kind=kind,
                    demand=n(row[demand_col]),capacity=n(row[capacity_col]),unit=unit,combination=f'原报告{level}'+('纵桥向' if direction=='longitudinal' else '横桥向'),
                    model_revision=REV,evidence='orig-53K',locator=f'原 DOCX 第{table+1}张表，第{row_no+1}行；{caption or "见源表快照"}',**extra)
        p['checks'].append(record);mappings.append({'check_id':record['id'],'table_index':table,'row_index':row_no,'demand_col':demand_col,'capacity_col':capacity_col,'source_row':row})
        return record
    def member_rows(table):
        groups={}
        for idx,row in enumerate(tables[table][1:],1):groups.setdefault(re.search(r'\d+',row[1]).group(),[]).append(idx)
        return groups
    for table,direction,prefix in [(11,'longitudinal','P'),(12,'longitudinal','F'),(15,'transverse','P'),(16,'transverse','F')]:
        for num,rows in member_rows(table).items():
            ri=min(rows,key=lambda i:n(tables[table][i][4])/n(tables[table][i][2]));row=tables[table][ri];cid=prefix+num;aid=f'E1-{cid}-{direction}'
            p['actions'].append(dict(id=aid,component=cid,direction=direction,level='E1',combination='原报告同一行配对内力',station=row[1],N_kN=n(row[2]),M_kNm=n(row[3])))
            r=add(table,ri,cid,direction,'E1','e1_capacity',2,4,'kN',action_id=aid,paired_N_M={'N_kN':n(row[2]),'M_kNm':n(row[3])},method='constant_eccentricity')
            r['combination']='原报告同一行配对内力'
    for table,direction,prefix,kind,dc,cc in [(20,'longitudinal','P','e2_moment',3,4),(21,'longitudinal','P','shear',2,3),
         (22,'longitudinal','F','e2_moment',3,4),(23,'longitudinal','F','shear',5,6),(27,'transverse','P','e2_moment',3,4),
         (28,'transverse','P','shear',2,3),(29,'transverse','F','e2_moment',3,4),(30,'transverse','F','shear',3,4)]:
        for num,rows in member_rows(table).items():
            ri=min(rows,key=lambda i:n(tables[table][i][cc])/n(tables[table][i][dc]))
            add(table,ri,prefix+num,direction,'E2',kind,dc,cc,'kN*m' if kind=='e2_moment' else 'kN', **({'axial_kN':n(tables[table][ri][2])} if kind=='e2_moment' else {}))
    for table,direction,level,kind in [(13,'longitudinal','E1','bearing_displacement'),(14,'longitudinal','E1','bearing_sliding'),
         (17,'transverse','E1','bearing_displacement'),(19,'transverse','E1','bearing_sliding'),(24,'longitudinal','E2','bearing_displacement'),
         (26,'longitudinal','E2','bearing_sliding'),(31,'transverse','E2','bearing_displacement'),(34,'transverse','E2','bearing_sliding')]:
        for ri,row in enumerate(tables[table][1:],1):add(table,ri,'B'+re.search(r'\d+',row[1]).group(),direction,level,kind,2,3,'m' if kind=='bearing_displacement' else 'kN')
    for table,level,suffix,unit in [(18,'E1','M','kN*m'),(32,'E2','M','kN*m'),(33,'E2','V','kN')]:
        for ri,row in enumerate(tables[table][1:],1):add(table,ri,'C'+re.search(r'\d+',row[1]).group()+suffix,'transverse',level,'additional',2,3,unit)
    for i in (1,2):p['not_applicable'].append(dict(component=f'C{i}V',direction='transverse',level='E1',kind='additional',reason='项目约定 E1 不开展抗剪验算，原报告亦无 E1 盖梁抗剪表',evidence='orig-53K'))
    p['detailing']={'level1':{'rows':[{'location':r[0],'design_cm':n(r[1]),'required_cm':n(r[2])} for r in tables[35][1:]]},'level2':[],'level3':[]}
    p['pilecap']={'necessity':'原报告未提供承台专项验算表，本次不推定承台验算结果。','checks':[]}
    p['selection']={'method':'按原报告同号双柱墩分组，各方向、各验算独立选最小能力/需求比；E1 N/M/容量始终来自同一行。','covered_components':[c['id'] for c in p['components']],
                    'limitations':'本次复现不替代第三步复算；原报告超强弯矩表缺少完整合同证据，因此不据该表解除能力保护待补正。原表全部保存在 source_tables。'}
    g=Golden(ref,OUT)
    p['overview']['figures']={'elevation':g.asset('fig-elevation',65,'K271+730桥梁立面图（原报告）'), 'pier':g.asset('fig-pier',74,'K271+730桥墩构造图（原报告）')}
    p['model']['figures']['fe_model']=g.asset('fig-fe-model',167,'K271+730有限元模型（原报告）')
    p['model']['figures']['bearing_layout']=g.asset('fig-bearing-layout',208,'支座垫石布置图（原报告）')
    p['model']['figures']['fiber_pile']=g.asset('fig-fiber-pile',252,'桩基截面纤维模型（原报告）',nth=0)
    p['model']['figures']['fiber_pier']=g.asset('fig-fiber-pier',252,'桥墩截面纤维模型（原报告）',nth=1)
    waves=[]
    for number,index in enumerate((142,144,146,148,150,152,154),1):
        try:waves.append(g.asset(f'fig-wave-{number}',index,f'原报告地震波 {number}'))
        except (IndexError,KeyError):pass
    p['seismic']['figures']['waves']=waves
    try:g.wave_spectra();p['seismic']['figures']['wave_spectra']='fig-wave-spectra'
    except (KeyError,StopIteration):pass
    for i,e in enumerate(ref.kids):
        if 215<i<240 and e.findall('.//'+q('drawing')):
            try:
                aid=g.asset(f'fig-mode-{i}',i,ref.text(i+1));p['modal']['figures'].append({'asset':aid,'caption':ref.text(i+1)})
            except IndexError:pass
    p['assets']=g.assets
    p['source_tables']=[{'table_index':i,'header':t[0],'rows':t[1:]} for i,t in enumerate(tables)]
    p['source_notes']=['原报告正文混凝土描述与材料表等级不一致；本次保留并提示专业复核。','纵桥向1#桩超强复算表需求3669.6、容量3006，但未提供合同要求的factor/reviewed/basis证据，不自动标记通过。','纵桥向2#桩弯矩3363.68大于容量3024，关联2#墩保持弹性；按既定流程停止后续验算。']
    issues=validate(p,OUT)
    if issues:raise ValueError(issues)
    result=evaluate(p,OUT)
    (OUT/'handoff.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'extraction-map.json').write_text(json.dumps({'source_sha256':source_hash,'records':mappings},ensure_ascii=False,indent=2),encoding='utf-8')
    index_path=ROOT/'examples/scenarios/index.json';index=json.loads(index_path.read_text(encoding='utf-8'));index=[e for e in index if e['id']!='golden-53K']
    index.insert(1,dict(id='golden-53K',title='53K271+730 原报告复现',group='golden',expected_status=result['status'],description='连续空心板梁桥、双柱墩：E2 桥墩进入塑性，桩基能力保护存在不满足及待补正，按流程停止后续验算。',file='golden/53K271+730/handoff.json',bridge_name='G8511昆磨高速 K271+730',checks_count=len(p['checks'])))
    index_path.write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
    print('53K:',result['status'],'checks',len(p['checks']),'assets',len(p['assets']),'issues',len(issues))
    return p


if __name__=='__main__':build()
