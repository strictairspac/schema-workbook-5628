import {table} from '../components/common/table.js';import {esc,date} from '../utils/html.js';import {session} from '../hooks/session.js';import {SYNC_STATES,SYNC_BLOCKED_REASONS} from '../constants/enums.js';

function stateCard(state){
  const pending=state.pending>0?`<p>源库还有 <strong>${state.pending}</strong> 笔提交等待接上。</p>`:'';
  const blocked=state.status==='blocked'?`<div class="error">${esc(SYNC_BLOCKED_REASONS[state.blocked_reason]||'同步暂停')}${state.missing_seq?`：缺少第 ${state.missing_seq} 号提交`:''}。${esc(state.error||'')} 复核库停留在第 ${state.cursor_seq} 号提交的可核对版本。</div>`:'';
  return `<div class="verdict"><div class="verdict-icon">${state.status==='ready'?'✓':state.status==='blocked'?'!':'…'}</div><div><span class="eyebrow">REVIEW SYNC</span><h2>${esc(SYNC_STATES[state.status]||state.status)}</h2><p>游标 ${state.cursor_seq} 号 · 基线 ${state.base_seq} 号 · 源库 ${state.source_seq} 号 · 已收下 ${state.counts.relations} 份草案 / ${state.counts.dependencies} 条依赖</p>${pending}</div></div>${blocked}`;
}

function relationsPanel(relations){
  return `<section><div class="section-top"><h2>复核库收下的草案</h2><span>${relations.length} 份 / REVIEW COPY</span></div>${table(['源编号 / 编号','属性集合','说明','落库于'],relations.map(r=>[`<strong>#${r.source_id} · ${esc(r.code)}</strong><small>${esc(r.title)}</small>`,r.attributes.map(a=>`<span class="attribute">${esc(a)}</span>`).join(' '),esc(r.note),`#${r.applied_seq}`]))}</section>`;
}

function dependenciesPanel(dependencies,relations){
  return `<section><div class="section-top"><h2>复核库收下的依赖</h2><span>${dependencies.length} 条 / REVIEW COPY</span></div>${table(['归属草案','函数依赖','业务依据','落库于'],dependencies.map(d=>[`#${d.relation_source_id} · ${esc(relations.find(r=>r.source_id===d.relation_source_id)?.code||'（草案已删除）')}`,`<strong>${esc(d.lhs.join(', ')||'∅')} → ${esc(d.rhs.join(', '))}</strong>`,esc(d.note),`#${d.applied_seq}`]))}</section>`;
}

function commitsPanel(commits){
  return `<section><div class="section-top"><h2>已应用提交</h2><span>${commits.length} 笔 / APPLIED</span></div>${table(['序号','操作', '操作人','改动数','落库时间'],commits.map(c=>[`#${c.seq}`,esc(c.action),esc(c.actor),c.change_count,date(c.applied_at)]))}</section>`;
}

export function syncPage(data){
  if(!data)return '<div class="empty">复核库状态加载中。</div>';
  const state=data.state,relations=data.relations,dependencies=data.dependencies,commits=data.commits;
  const writable=session.user.role!=='viewer';
  const isAdmin=session.user.role==='admin';
  const copyDone=state.status!=='empty';
  return `${stateCard(state)}
  <div class="split"><section>
    <div class="protocol"><h3>同步规则</h3><ol><li>初次复制先取基线序号再整册复制，复制期间原库照常编辑</li><li>增量从上次落库的游标接着传，整笔提交到齐才可见</li><li>依赖改归属时以新归属替换旧归属，回滚的事务不传</li><li>重复投递按提交编号跳过；断档则暂停并保留最后可核对版本</li></ol></div>
    ${relationsPanel(relations)}${dependenciesPanel(dependencies,relations)}${commitsPanel(commits)}
  </section><section class="form-panel">
    <span class="eyebrow">INCREMENTAL REVIEW</span><h2>同步操作</h2>
    <p class="help">复核库只读地跟随源库；这里收下的是复核库实际落库的草案与依赖，不是源库当前值。</p>
    <button id="sync-bootstrap" class="primary" ${writable&&!copyDone?'':'disabled'}>初次复制全库</button>
    <button id="sync-pull" class="primary" ${writable&&copyDone?'':'disabled'}>接上增量</button>
    ${isAdmin?`<button id="sync-reset" ${copyDone?'':'disabled'}>清空复核库（演示）</button>`:''}
    <p class="help" id="sync-hint">${state.status==='syncing'||state.pending>0?'还有提交待接上，点击“接上增量”。':state.status==='ready'?'已追平源库。':state.status==='blocked'?'修复缺号后可再次“接上增量”。':'先执行初次复制。'}</p>
  </section></div>`;
}
