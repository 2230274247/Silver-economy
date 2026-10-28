"""Offline HTML reports; no external assets, tracking, model calls or private credentials."""

# HTML/CSS templates keep each element together; Python expressions still use normal formatting.
# ruff: noqa: E501

import html
import json
from pathlib import Path


def escaped(value):
    return html.escape(str(value), quote=True)


def percent(value):
    return "未测量" if value is None else f"{value * 100:.1f}%"


def render_report(report, comparison=None):
    options = "".join(
        f'<option value="{r["scale"]}">{r["scale"]:,} 条</option>' for r in report["scales"]
    )
    summary = []
    sections = []
    for run in report["scales"]:
        metric = run["metrics"]
        scale = run["scale"]
        verdict = all(run["gates"].values())
        counts = run.get("per_user_memory_counts")
        population = (
            " / ".join(f"{escaped(actor)} {count:,}" for actor, count in counts.items())
            if counts
            else f"人均 {run['per_user_memories_before']:,}"
        )
        summary.append(f'''<tr><th scope="row">{scale:,}<small>{population}</small></th>
        <td>{percent(metric["recall_at_5"])}</td><td>{percent(metric["top1_accuracy"])}</td>
        <td>{percent(metric["answer_accuracy_mock"])}</td><td>{percent(metric["conflict_accuracy_mock"])}</td>
        <td>{percent(metric["unsupported_answer_rate_mock"])}</td><td>{metric["retrieval_p95_ms"]:.1f} ms</td>
        <td>{metric["cross_user_leakage"]} / {metric["deleted_memory_recall"]}</td>
        <td class="{"pass" if verdict else "fail"}">{"通过门禁" if verdict else "未达全部门禁"}</td></tr>''')
        gates = "".join(
            f'<li><span class="{"pass" if ok else "fail"}">{"通过" if ok else "未通过"}</span> {escaped(name)}</li>'
            for name, ok in run["gates"].items()
        )
        groups = "".join(
            f'<tr><th scope="row">{escaped(name)}</th><td>{v["cases"]}</td><td>{percent(v["answer_accuracy_mock"])}</td></tr>'
            for name, v in run["groups"].items()
        )
        failures = [c for c in run["cases"] if not c["answer_correct"]]
        rows = "".join(
            f"""<tr><th scope="row">{escaped(c["id"])}<small>{escaped(c["actor"])} · {escaped(c["group"])}</small></th>
        <td>{escaped(c["question"])}</td><td>{escaped(", ".join(c["expected"]) or "应明确承认未知")}</td>
        <td>{escaped(", ".join(c["retrieved"]) or "无")}</td><td>{escaped(c["reply"])}</td>
        <td>{escaped(c["error"] or "")}</td></tr>"""
            for c in failures
        )
        resource = run["resources"]
        concurrent = run["concurrency"]
        previous = ""
        if comparison:
            prior = next((v for v in comparison["scales"] if v["scale"] == scale), None)
            if prior:
                same = prior["initial_snapshot"] == run["initial_snapshot"]
                previous = f"""<p class="note">与 {escaped(comparison["label"])} 比较：固定题集
                {"一致" if report["suite_sha256"] == comparison["suite_sha256"] else "不一致"}；初始事实快照
                {"一致" if same else "不同，不能当作相同数据上的排序对比"}。
                Recall@5 {percent(prior["metrics"]["recall_at_5"])} → {percent(metric["recall_at_5"])}；
                Top-1 {percent(prior["metrics"]["top1_accuracy"])} → {percent(metric["top1_accuracy"])}。</p>"""
        sections.append(f'''<section class="scale" data-scale="{scale}"><h2>{scale:,} 条结构化记忆</h2>
        <p>固定问题 {len(run["cases"])} · 干扰与受控事实均在独立测试库 · 准备 {run["preparation_seconds"]:.2f} 秒</p>{previous}
        <div class="columns"><div class="card"><h3>门禁</h3><ul class="gates">{gates}</ul></div>
        <div class="card"><h3>分组回答正确率（Mock）</h3><table><thead><tr><th>分组</th><th>题数</th><th>正确率</th></tr></thead><tbody>{groups}</tbody></table></div></div>
        <div class="card"><h3>性能与资源</h3><dl>
        <dt>检索 P50 / P95</dt><dd>{metric["retrieval_p50_ms"]} / {metric["retrieval_p95_ms"]} ms</dd>
        <dt>实际聊天接口 P95（Mock）</dt><dd>{metric["chat_api_p95_ms_mock"]} ms</dd>
        <dt>检索 SQL 次数 / 累计执行时间</dt><dd>{metric["sql_queries"]:,} / {metric["sql_total_ms"]:.1f} ms</dd>
        <dt>并发稳定性</dt><dd>{concurrent["workers"]} workers · {concurrent["requests"]} 次 · P95 {concurrent["retrieval_p95_ms"]} ms · 泄漏 {concurrent["cross_user_leakage"]}</dd>
        <dt>Python 分配峰值（评估增量）</dt><dd>{resource["python_allocated_peak_bytes"] / 1048576:.2f} MiB</dd>
        <dt>进程生命周期最高工作集</dt><dd>{escaped(resource.get("peak_rss_lifetime_bytes"))} bytes</dd>
        <dt>CPU / 评估墙钟时间</dt><dd>{resource["python_cpu_seconds"]:.2f} / {resource["evaluation_wall_seconds"]:.2f} 秒</dd>
        <dt>最大上下文 / 证据条数</dt><dd>{metric["max_prompt_bytes"]:,} UTF-8 bytes / {metric["max_evidence_items"]}</dd>
        <dt>真实模型调用 / 接口错误</dt><dd>{metric["real_model_calls"]} / {metric["errors"]}</dd>
        <dt>初始 / 最终事实数</dt><dd>{run["initial_snapshot"]["memories"]:,} / {run["final_snapshot"]["memories"]:,}</dd>
        </dl></div>
        <details><summary>未正确回答的用例（{len(failures)}）</summary><div class="table-scroll"><table class="cases"><thead><tr><th>编号</th><th>问题</th><th>标准来源</th><th>实际检索</th><th>完整或前500字回复</th><th>错误</th></tr></thead><tbody>{rows}</tbody></table></div></details></section>''')
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>记忆评估 · {escaped(report["label"])}</title>
    <style>:root{{color-scheme:light;--ink:#213b34;--muted:#52675f;--green:#367365;--cream:#f5f7f1;--line:#d7e2d9}}*{{box-sizing:border-box}}body{{margin:0;background:var(--cream);color:var(--ink);font-family:system-ui,'Microsoft YaHei',sans-serif;line-height:1.65}}main{{max-width:1360px;margin:auto;padding:36px 28px}}header{{padding-bottom:24px}}h1{{font-size:clamp(28px,4vw,46px);line-height:1.25;margin:10px 0}}h2{{margin-top:0}}h3{{margin-top:0}}.tag{{display:inline-block;padding:5px 12px;border-radius:99px;background:#e0ece2;color:#254c3e;font-weight:650}}p{{max-width:100ch}}.note,small{{color:var(--muted)}}small{{display:block;font-weight:400}}.card,section{{background:white;border:1px solid var(--line);border-radius:18px;padding:24px;margin:18px 0}}section{{margin-top:32px}}section .card{{margin:12px 0;background:#f8faf6}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.pass{{color:#246442;font-weight:700}}.fail{{color:#9b362b;font-weight:700}}.gates{{list-style:none;margin:0;padding:0;columns:2}}.gates li{{margin:6px 0;break-inside:avoid}}.table-scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;text-align:left;font-size:15px}}th,td{{padding:12px 10px;vertical-align:top;border-bottom:1px solid var(--line)}}thead{{background:#edf3ed}}.summary{{min-width:1100px}}.cases{{min-width:1200px;table-layout:fixed}}.cases th:first-child{{width:130px}}.cases td{{overflow-wrap:anywhere}}select{{font:inherit;background:white;color:var(--ink);border:1px solid #9bb5a6;border-radius:10px;padding:10px 14px;margin-left:10px;min-height:46px}}summary{{cursor:pointer;padding:12px 0;font-weight:650}}dl{{display:grid;grid-template-columns:1fr 2fr;gap:10px}}dt{{color:var(--muted)}}dd{{margin:0;overflow-wrap:anywhere}}code{{overflow-wrap:anywhere}}footer{{margin:30px 0;color:var(--muted)}}@media(max-width:750px){{main{{padding:22px 16px}}.columns{{grid-template-columns:1fr}}section,.card{{padding:18px}}.gates{{columns:1}}dl{{grid-template-columns:1fr}}dd{{margin-bottom:8px}}}}</style></head>
    <body><main><header><span class="tag">Synthetic · Mock · 真实模型调用 0</span><h1>长期记忆质量与性能评估</h1><p>运行：{escaped(report["label"])} · {escaped(report["created_at_hk"])} · 状态：{escaped(report["status"])}</p>
    <p>固定 {report["suite_questions"]} 个用例、{report["unique_question_texts"]} 种不同问法。真实 MySQL、登录/新会话/持久化与刷新链路；答案由独立闭合标准及来源ID计分，未用LLM自评。</p>
    <p class="note">“无依据回答率”是未知问题未明确承认不确定的保守 Mock 代理指标，不能当作真实 DeepSeek 的通用幻觉率。进程内存包含准备阶段，Python分配峰值仅覆盖评估。这里的检索延迟与导入耗时不同。</p>
    <p><strong>题集 SHA-256</strong><br><code>{escaped(report["suite_sha256"])}</code></p></header>
    <div class="card table-scroll"><table class="summary"><thead><tr><th>事实数</th><th>Recall@5</th><th>Top-1</th><th>回答正确率<br>Mock</th><th>冲突正确率<br>Mock</th><th>无依据回答率<br>Mock代理</th><th>检索P95</th><th>泄漏/删除召回</th><th>门禁</th></tr></thead><tbody>{"".join(summary)}</tbody></table></div>
    <label for="scale">查看规模<select id="scale"><option value="all">全部规模</option>{options}</select></label>{"".join(sections)}
    <footer>所有人物与生活事实均为合成。Mock结果与真实模型样本分开；未达指标的原始结果保留。完整指标和逐题来源见同名JSON文件。</footer></main>
    <script>document.getElementById('scale').addEventListener('change',function(){{document.querySelectorAll('.scale').forEach(s=>s.hidden=this.value!=='all'&&s.dataset.scale!==this.value)}})</script></body></html>"""


def write_report(path, comparison=None):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    previous = json.loads(Path(comparison).read_text(encoding="utf-8")) if comparison else None
    raw = render_report(data, previous).encode()
    target = path.with_suffix(".html")
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Preserve prior HTML evidence; use a new run label")
    if not target.exists():
        with target.open("xb") as file:
            file.write(raw)
    return target
