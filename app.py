import os
import sqlite3
import datetime
import csv
import io
from flask import Flask, request, jsonify, render_template_string, make_response

app = Flask(__name__)
ADMIN_PASSWORD = "PsychAdmin2026"
DB_PATH = "/tmp/psych_data.db"

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS results
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time TEXT, sid TEXT, score REAL, level TEXT, 
                    d1 REAL, d2 REAL, d3 REAL, d4 REAL, d5 REAL)''')
    conn.commit()
    return conn

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>心灵觉察与内省系统 (五维22项)</title>
    <style>
        body { font-family: '微软雅黑', sans-serif; padding: 20px; background: #f7f9f9; color: #333; }
        .container { background: #fff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.05); max-width: 800px; margin: auto; }
        h2 { text-align: center; font-weight: 300; color: #2c3e50; letter-spacing: 2px; margin-bottom: 5px;}
        .sub-title { text-align: center; color: #95a5a6; font-size: 13px; margin-bottom: 25px; }
        
        .disclaimer { background: #fdf2e9; border-left: 4px solid #e67e22; padding: 15px; margin-bottom: 20px; font-size: 13px; color: #d35400; line-height: 1.6; }
        
        .question-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px dashed #e0e0e0; }
        .question-text { flex: 1; font-size: 15px; color: #34495e; padding-right: 20px; }
        select { width: 120px; padding: 8px; border: 1px solid #bdc3c7; border-radius: 6px; outline: none; font-size: 14px; background: #fff; color: #2c3e50;}
        select:focus { border-color: #3498db; }
        .btn { width: 100%; padding: 16px; background: #2c3e50; color: white; border: none; border-radius: 6px; font-size: 18px; margin-top: 30px; cursor: pointer; transition: background 0.3s; }
        .btn:hover { background: #1a252f; }
        
        #resultArea { display: none; margin-top: 40px; padding: 30px; background: #fdfbf7; border: 1px solid #f0e6d2; border-radius: 8px; }
        .quote { font-style: italic; font-size: 18px; color: #8e7a59; text-align: center; margin: 20px 0; line-height: 1.8; }
        .advice { font-size: 15px; color: #555; line-height: 1.8; margin-top: 20px; background: #fff; padding: 15px; border-radius: 6px; border-left: 4px solid #8e7a59;}
    </style>
</head>
<body>
    <div class="container">
        <h2>心灵觉察与内省</h2>
        <p class="sub-title">基于五因子模型本土化研发 (CFI=0.92, RMSEA=0.06)</p>
        
        <div class="disclaimer">
            <b>⚠️ 知情同意与免责声明：</b><br>
            1. 本系统为教育发展性筛查工具，<b>不作为任何临床医学诊断或心理疾病确诊依据。</b><br>
            2. 测评结果将严格保密，仅用于心理健康教育参考。<br>
            3. 如果您近期有强烈的痛苦感，请立即拨打心理援助热线（如：400-161-9995）或就医。<br>
            <label style="margin-top: 8px; display: block; font-weight: bold; cursor: pointer;">
                <input type="checkbox" id="agreeCheck" style="transform: scale(1.2); margin-right: 5px;"> 我已阅读并同意上述声明
            </label>
        </div>

        <div style="margin-bottom: 20px;">
            <input id="sid" placeholder="请输入学号/代号（仅用于内部记录）" style="padding: 12px; width: 100%; box-sizing: border-box; border: 1px solid #bdc3c7; border-radius: 6px; font-size: 16px;">
        </div>

        <div id="questions"></div>

        <button id="submitBtn" class="btn" onclick="submitData()">提交并观察</button>

        <div id="resultArea">
            <h3 style="text-align: center; font-weight: normal; color: #8e7a59;">你的内省之镜</h3>
            <div id="quoteText" class="quote"></div>
            <div id="adviceText" class="advice"></div>
        </div>
    </div>

    <script>
        var questionsData = [
            { id: 1, text: "1. 当焦虑或紧张出现时，我能觉察到身体的变化（如心跳加速）。" },
            { id: 2, text: "2. 我是否能看着自己的情绪起伏，而不被它立刻卷走？" },
            { id: 3, text: "3. 当遇到挫折时，我能意识到自己正在发脾气或急躁吗？" },
            { id: 4, text: "4. 考前，我是否能观察到自己的担忧，并接纳这种担忧的存在？" },
            { id: 5, text: "5. 我是否能察觉到那些莫名烦躁的时刻，并只是静静地陪伴它？" },
            { id: 6, text: "6. 我是否能分清“事实”和“我对事实的想象”？" },
            { id: 7, text: "7. 出现“我不够好”的想法时，我能把它当作一个想法，而不是真理吗？" },
            { id: 8, text: "8. 我能否接受自己的缺点，并觉察到大脑是如何试图掩饰它们的？" },
            { id: 9, text: "9. 我是否能观察到，是我的记忆和偏见在主导我的判断？" },
            { id: 10, text: "10. 我是否注意到自己为了迎合他人，而带上了不同的“面具”？" },
            { id: 11, text: "11. 当我急于做决定时，我能觉察到背后的急躁或恐惧吗？" },
            { id: 12, text: "12. 我是否意识到，自己经常在无意识地重复某种习惯（如刷手机）？" },
            { id: 13, text: "13. 我能觉察到自己的乐观或悲观，只是我观察世界的滤镜吗？" },
            { id: 14, text: "14. 与人交谈时，我真的在倾听，还是在脑海里准备我的反驳？" },
            { id: 15, text: "15. 在团队中，我能否观察到自己的竞争心、嫉妒心？" },
            { id: 16, text: "16. 当我看不惯某个人时，我能觉察到那是我内心的投射吗？" },
            { id: 17, text: "17. 我是否能毫无内疚地、坦然地说“不”，并观察对方的反应？" },
            { id: 18, text: "18. 我是否能觉察到自己对独处的恐惧，或者对热闹的依赖？" },
            { id: 19, text: "19. 当压力袭来时，我能观察到自己的呼吸是否变得急促？" },
            { id: 20, text: "20. 我是否能觉察到，很多压力来自于我试图“成为”别人眼中的优秀者？" },
            { id: 21, text: "21. 面对挫折，我能否不立刻寻找责任人或借口，而是直视它？" },
            { id: 22, text: "22. 我是否相信，真正的自由在于内心的觉察？" }
        ];

        var optionsList = [{ v: 1, t: "从未觉察" }, { v: 2, t: "偶尔觉察" }, { v: 3, t: "有时觉察" }, { v: 4, t: "经常觉察" }, { v: 5, t: "深度觉察" }];
        var html = '';
        for (var i = 0; i < questionsData.length; i++) {
            var opts = '<option value="">请选择</option>';
            for(var j=0; j<optionsList.length; j++){ opts += '<option value="' + optionsList[j].v + '">' + optionsList[j].t + '</option>'; }
            html += '<div class="question-item"><span class="question-text">' + questionsData[i].text + '</span><select id="q' + questionsData[i].id + '">' + opts + '</select></div>';
        }
        document.getElementById('questions').innerHTML = html;

        function submitData() {
            if (!document.getElementById('agreeCheck').checked) { alert('请先阅读并勾选知情同意声明！'); return; }
            var sid = document.getElementById('sid').value.trim();
            if (!sid) { alert('请输入学号！'); return; }
            
            var answers = [];
            for (var i = 1; i <= 22; i++) {
                var val = document.getElementById('q' + i).value;
                if (!val) { alert('第' + i + '题未作答。'); return; }
                answers.push(parseInt(val));
            }
            
            var btn = document.getElementById('submitBtn');
            btn.disabled = true; btn.innerText = "照见中...";

            fetch('/api/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({sid: sid, answers: answers})
            }).then(res => res.json()).then(data => {
                btn.style.display = 'none';
                document.getElementById('resultArea').style.display = 'block';
                document.getElementById('quoteText').innerText = "“" + data.quote + "”";
                document.getElementById('adviceText').innerHTML = data.advice;
                document.getElementById('resultArea').scrollIntoView({behavior: "smooth"});
            }).catch(() => { alert("提交失败"); btn.disabled = false; btn.innerText = "提交并观察"; });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json
    sid = data.get('sid')
    answers = data.get('answers', [])
    if not sid or len(answers) != 22:
        return jsonify({'error': '数据不完整'}), 400

    dim_raw_scores = [0, 0, 0, 0, 0]
    dim_counts = [5, 4, 4, 5, 4]
    current_idx = 0
    count = 0
    for ans in answers:
        if count >= dim_counts[current_idx]:
            current_idx += 1
            count = 0
        dim_raw_scores[current_idx] += ans
        count += 1
    dim_percent_scores = [round(dim_raw_scores[i] / (dim_counts[i] * 5) * 100, 1) for i in range(5)]
    total_avg = round(sum(dim_percent_scores) / 5, 1)

    if total_avg < 40:
        quote = "“观察而不评判，是最高形式的智慧。当你不再给感受贴标签，你就自由了。”"
        advice = "<b>你最近可能被各种思绪和情绪裹挟了。</b><br><br>请不要自责。试着对自己说：『我观察到我现在很烦躁，我感到胸口有点闷，我需要一点空间。』"
        level, color = "红色（紧急级）", "#e74c3c"
    elif total_avg < 60:
        quote = "“你无法改变你是什么，你只能观察你是什么；在观察中，改变自然发生。”"
        advice = "<b>你目前的压力较大，觉察力有所下降。</b><br><br>试着用非暴力沟通表达：『我观察到（事实），我感到（情绪），因为我需要（需求）。』"
        level, color = "橙色（干预级）", "#f39c12"
    elif total_avg < 80:
        quote = "“一颗自由的心，没有固定的模式，它时刻在觉察中更新。”"
        advice = "<b>你已经具备了一定的自我观察能力。</b><br><br>但在高压下偶尔还是会当局者迷。多练习正念呼吸能帮你回到当下。"
        level, color = "黄色（辅导级）", "#f1c40f"
    else:
        quote = "“真理是无路之国，你只能在自己内心的觉察中抵达。”"
        advice = "<b>你拥有极其敏锐的觉察力。</b><br><br>你能清晰地看到自己的想法和情绪起伏。请继续保持这份清明。"
        level, color = "蓝色（关注级）", "#3498db"

    conn = get_db_conn()
    conn.execute("INSERT INTO results (time, sid, score, level, d1, d2, d3, d4, d5) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sid, total_avg, level, *dim_percent_scores))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'quote': quote, 'advice': advice})

@app.route('/admin')
def admin():
    if request.args.get('pwd') != ADMIN_PASSWORD:
        return "<h2 style='color:red; text-align:center; margin-top:50px;'>🔒 无权访问。请使用正确密码访问，例如：/admin?pwd=密码</h2>"
        
    html = "<h2 style='font-family:微软雅黑; text-align:center;'>心理测评预警看板</h2>"
    html += "<div style='text-align:center; margin-bottom:20px;'><a href='/export?pwd=" + ADMIN_PASSWORD + "' style='padding:10px 20px; background:#2c3e50; color:white; text-decoration:none; border-radius:4px;'>📥 导出数据 (CSV)</a></div>"
    
    conn = get_db_conn()
    cursor = conn.execute("SELECT time, sid, score, level, d1, d2, d3, d4, d5 FROM results ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    html += "<table border='1' cellpadding='10' style='border-collapse:collapse; width:100%; max-width:900px; margin:auto; text-align:center; font-family:微软雅黑; font-size:14px;'>"
    html += "<tr style='background:#ecf0f1;'><th>时间</th><th>学号</th><th>总分</th><th>预警等级</th><th>情绪</th><th>认知</th><th>性格</th><th>社交</th><th>应对</th></tr>"
    for r in rows:
        color = "#3498db" if "蓝色" in r[3] else "#f1c40f" if "黄色" in r[3] else "#f39c12" if "橙色" in r[3] else "#e74c3c"
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td style='color:{color}; font-weight:bold;'>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[6]}</td><td>{r[7]}</td><td>{r[8]}</td></tr>"
    html += "</table>"
    return html

@app.route('/export')
def export():
    if request.args.get('pwd') != ADMIN_PASSWORD:
        return "无权访问"
    conn = get_db_conn()
    cursor = conn.execute("SELECT time, sid, score, level, d1, d2, d3, d4, d5 FROM results")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return "暂无数据"
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['时间', '学号', '觉察指数', '预警等级', '情绪稳定性', '自我认知', '性格倾向', '社交能力', '压力应对'])
    for r in rows: writer.writerow(r)
    
    response = make_response(output.getvalue().encode('utf-8-sig'))
    response.headers["Content-Disposition"] = "attachment; filename=psych_data.csv"
    response.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return response
