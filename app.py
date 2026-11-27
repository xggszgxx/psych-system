import os
import sqlite3
import datetime
import csv
import io
import urllib.parse
from urllib.parse import quote
from flask import Flask, request, jsonify, render_template_string, make_response, send_file
from flask_cors import CORS
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

# ==================== 初始化配置 ====================
app = Flask(__name__)
CORS(app)  # 👈 允许所有跨域请求（解决小程序/网页跨域问题）

ADMIN_PASSWORD = "PsychAdmin2026"
DB_PATH = "/tmp/psych_data.db"

# 维度名称配置
DIM_NAMES = ["情绪稳定性", "自我认知", "性格倾向", "社交能力", "压力应对"]

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS results
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time TEXT, sid TEXT, score REAL, level TEXT,
                    d1 REAL, d2 REAL, d3 REAL, d4 REAL, d5 REAL,
                    positive_count INTEGER DEFAULT 0)''')
    try:
        conn.execute("ALTER TABLE results ADD COLUMN positive_count INTEGER DEFAULT 0")
    except:
        pass
    conn.commit()
    return conn

def generate_intelligent_analysis(score, level, positive_count, d_scores):
    # 识别超标维度（<40分即能力不足）
    over_dims = []
    for i in range(5):
        if d_scores[i] < 40:
            over_dims.append(DIM_NAMES[i])
    over_count = len(over_dims)
    over_dims_str = "、".join(over_dims) if over_dims else "无"

    # 识别无效作答
    is_invalid = (positive_count == 22) or (positive_count == 0 and score < 95)

    if is_invalid:
        return "⚠️ 高度疑似随意作答（答案模式异常），不计入统计，请单独约谈核实是否如实作答。"
    elif "红色" in level:
        return f"总分{score}，阳性项目{positive_count}项。{over_count}个因子超标({over_dims_str})。建议立即进行专业心理评估与干预。"
    elif "橙色" in level:
        return f"总分{score}，阳性项目{positive_count}项。{over_count}个因子超标({over_dims_str})。建议一周内开展一对一/小组心理辅导，两周后复测。"
    elif "黄色" in level:
        return f"总分{score}，阳性项目{positive_count}项。待提升维度：{over_dims_str}。建议关注情绪变化，适当自我调节。"
    else:
        return "各项指标均在正常范围内，心理健康状况良好。"

# ==================== 网页端 HTML ====================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
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
            1. 本系统为教育发展性筛查工具，不作为任何临床医学诊断或心理疾病确诊依据。<br>
            2. 测评结果将严格保密，仅用于心理健康教育参考。<br>
            3. 如果您近期有强烈的痛苦感，请立即拨打心理援助热线（如：400-161-9995）或就医。
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
            fetch('/api/psych/submit', {
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

# ==================== 提交测评接口 ====================
@app.route('/api/psych/submit', methods=['POST', 'OPTIONS'])
def submit():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}) # 处理跨域预检请求
        
    data = request.json
    # 兼容小程序传的 student_id 和网页传的 sid
    sid = data.get('student_id') or data.get('sid') 
    answers = data.get('answers', [])
    
    # 兼容小程序传的字典格式 { "1": 5 } 和网页传的列表格式 [5, 4, 3...]
    if isinstance(answers, dict):
        ans_list = [answers.get(str(i), 3) for i in range(1, 23)]
    else:
        ans_list = answers

    if not sid or len(ans_list) != 22:
        return jsonify({'error': '数据不完整', 'status': 'fail'}), 400

    # 计算五维得分
    dim_raw_scores = [0, 0, 0, 0, 0]
    dim_counts = [5, 4, 4, 5, 4]
    current_idx = 0
    count = 0
    for ans in ans_list:
        if count >= dim_counts[current_idx]:
            current_idx += 1
            count = 0
        dim_raw_scores[current_idx] += ans
        count += 1
        
    dim_percent_scores = [round(dim_raw_scores[i] / (dim_counts[i] * 5) * 100, 1) for i in range(5)]
    total_avg = round(sum(dim_percent_scores) / 5, 1)

    # 计算阳性项目数
    positive_count = sum(1 for ans in ans_list if ans <= 2)

    # 判定预警等级
    if total_avg < 40:
        quote = "“观察而不评判，是最高形式的智慧。当你不再给感受贴标签，你就自由了。”"
        advice = "你最近可能被各种思绪和情绪裹挟了。</b>请不要自责。试着对自己说：『我观察到我现在很烦躁，我感到胸口有点闷，我需要一点空间。』"
        level, color, risk_word = "红色（紧急级）", "#e74c3c", "红"
    elif total_avg < 60:
        quote = "“你无法改变你是什么，你只能观察你是什么；在观察中，改变自然发生。”"
        advice = "你目前的压力较大，觉察力有所下降。</b>试着用非暴力沟通表达：『我观察到（事实），我感到（情绪），因为我需要（需求）。』"
        level, color, risk_word = "橙色（干预级）", "#f39c12", "橙"
    elif total_avg < 80:
        quote = "“一颗自由的心，没有固定的模式，它时刻在觉察中更新。”"
        advice = "你已经具备了一定的自我观察能力。</b>但在高压下偶尔还是会当局者迷。多练习正念呼吸能帮你回到当下。"
        level, color, risk_word = "黄色（辅导级）", "#f1c40f", "黄"
    else:
        quote = "“真理是无路之国，你只能在自己内心的觉察中抵达。”"
        advice = "你拥有极其敏锐的觉察力。</b>你能清晰地看到自己的想法和情绪起伏。请继续保持这份清明。"
        level, color, risk_word = "蓝色（关注级）", "#3498db", "蓝"

    # 存入数据库
    conn = get_db_conn()
    conn.execute("INSERT INTO results (time, sid, score, level, d1, d2, d3, d4, d5, positive_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sid, total_avg, level, *dim_percent_scores, positive_count))
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success', 
        'quote': quote, 
        'advice': advice,
        'risk': risk_word,
        'scores': {
            'emotion': dim_percent_scores[0],
            'cognition': dim_percent_scores[1],
            'personality': dim_percent_scores[2],
            'social': dim_percent_scores[3],
            'stress': dim_percent_scores[4]
        },
        'total': total_avg
    })

# ==================== 后台管理看板 ====================
@app.route('/admin')
def admin():
    if request.args.get('pwd') != ADMIN_PASSWORD:
        return "<h2 style='color:red; text-align:center; margin-top:50px;'>🔒 无权访问。请使用正确密码访问，例如：/admin?pwd=密码</h2>"

    html = "<h2 style='font-family:微软雅黑; text-align:center;'>心理测评预警看板</h2>"
    html += "<div style='text-align:center; margin-bottom:20px;'>"
    html += f"<a href='/export?pwd={quote(ADMIN_PASSWORD)}' style='padding:10px 20px; background:#2c3e50; color:white; text-decoration:none; border-radius:4px; margin-right:10px;'>📥 导出数据 (CSV)</a>"
    html += "<span style='color:#7f8c8d; font-size:14px;'>系统自动生成智能分析与干预建议</span>"
    html += "</div>"

    conn = get_db_conn()
    cursor = conn.execute("SELECT time, sid, score, level, d1, d2, d3, d4, d5, positive_count FROM results ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    html += "<table border='1' cellpadding='8' style='border-collapse:collapse; width:98%; margin:auto; text-align:center; font-family:微软雅黑; font-size:13px;'>"
    html += "<tr style='background:#ecf0f1;'>"
    html += "<th>时间</th><th>学号</th><th>总分</th><th>预警等级</th><th>情绪</th><th>认知</th><th>性格</th><th>社交</th><th>应对</th><th>阳性项目数</th><th style='width:350px;'>智能分析</th>"
    html += "</tr>"

    for r in rows:
        time, sid, score, level, d1, d2, d3, d4, d5, positive_count = r
        d_scores = [d1, d2, d3, d4, d5]
        analysis = generate_intelligent_analysis(score, level, positive_count, d_scores)
        level_color = "#3498db" if "蓝色" in level else "#f1c40f" if "黄色" in level else "#f39c12" if "橙色" in level else "#e74c3c"
        bg_color = "#fef5f5" if "红色" in level else "#fffbf0" if "橙色" in level else "#fefff0" if "黄色" in level else "#f0f8ff"

        html += f"<tr style='background:{bg_color};'>"
        html += f"<td>{time}</td>"
        html += f"<td>{sid}</td>"
        html += f"<td>{score}</td>"
        html += f"<td style='color:{level_color}; font-weight:bold;'>{level}</td>"
        html += f"<td>{d1}</td><td>{d2}</td><td>{d3}</td><td>{d4}</td><td>{d5}</td>"
        html += f"<td>{positive_count}</td>"
        
        # 智能分析列 & 红色预警下载按钮
        html += "<td style='text-align:left; font-size:12px; line-height:1.5; padding:8px;'>"
        html += f"<div>{analysis}</div>"
        if "红色" in level:
            html += f"<a href='/admin/download_agreement?sid={sid}&score={score}' target='_blank' style='display:inline-block; margin-top:10px; padding:6px 12px; background-color:#e74c3c; color:white; text-decoration:none; border-radius:4px; font-weight:bold; font-size:13px;'>📄 下载家校安全协议</a>"
        html += "</td>"
        
        html += "</tr>"
    html += "</table>"
    return html

# ==================== 导出 CSV ====================
@app.route('/export')
def export():
    if request.args.get('pwd') != ADMIN_PASSWORD:
        return "无权访问"
    conn = get_db_conn()
    cursor = conn.execute("SELECT time, sid, score, level, d1, d2, d3, d4, d5, positive_count FROM results ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return "暂无数据"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['时间', '学号', '觉察指数', '预警等级', '情绪稳定性', '自我认知', '性格倾向', '社交能力', '压力应对', '阳性项目数', '智能分析'])
    for r in rows:
        time, sid, score, level, d1, d2, d3, d4, d5, positive_count = r
        d_scores = [d1, d2, d3, d4, d5]
        analysis = generate_intelligent_analysis(score, level, positive_count, d_scores)
        writer.writerow(list(r) + [analysis])

    response = make_response(output.getvalue().encode('utf-8-sig'))
    response.headers["Content-Disposition"] = "attachment; filename=psych_data.csv"
    response.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return response

# ==================== 📄 生成并下载 Word 安全协议 ====================
@app.route('/admin/download_agreement')
def download_agreement():
    sid = request.args.get('sid', '某某同学')
    score = request.args.get('score', '20.0')
    date_str = datetime.datetime.now().strftime('%Y年%m月%d日')

    doc = Document()
    
    # 设置全局字体
    doc.styles['Normal'].font.name = u'宋体'
    doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), u'宋体')

    # 标题
    title = doc.add_heading('家校共建学生心理健康安全协议', level=0)
    title.alignment = 1
    for run in title.runs:
        run.font.name = u'黑体'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), u'黑体')

    doc.add_paragraph(f'甲方（学校）：湖西学校 / 单县舜师高中')
    doc.add_paragraph(f'乙方（学生监护人）：__________________（学生：{sid}）')
    doc.add_paragraph(f'签订日期：{date_str}')
    doc.add_paragraph('')
    
    content_paragraphs = [
        f'鉴于近期学校在开展的心理健康普查中，测评系统提示该生（学号/代号：{sid}，综合预警指数：{score}分）存在一定的心理危机风险。为保障学生的心理健康与生命安全，明确学校与家庭在学生心理危机干预中的责任与义务，经甲乙双方友好协商，达成如下协议：',
        '',
        '一、 甲方的权利与义务',
        '1. 甲方有义务向乙方如实反馈学生在校的心理测评结果及日常行为表现。',
        '2. 甲方应尽最大努力在校内为学生提供心理辅导、危机干预、同伴支持及必要的安全监护。',
        '3. 甲方有义务对学生的心理档案进行严格保密（保密例外原则除外：如涉及自伤、伤人、违法等情况，学校有权上报相关部门）。',
        '4. 甲方不得因学生存在心理困扰而歧视学生或违规剥夺其受教育权。',
        '',
        '二、 乙方的权利与义务',
        '1. 乙方（家长）作为学生的法定监护人，是学生心理安全的第一责任人。',
        '2. 乙方在收到甲方通知后，应于 24 小时内配合学校，带学生前往专业医疗机构（如精神卫生中心、三甲医院心理科）进行权威诊断，并及时将诊断结果反馈给学校。',
        '3. 乙方应遵照医嘱督促学生按时服药、定期复诊，不得擅自停药。',
        '4. 乙方在家庭中应做好学生的 24 小时安全监护，严防自伤、自杀等极端事件发生。',
        '',
        '三、 危机处置与休复学机制',
        '1. 若学生出现急性心理危机，甲方将立即启动应急预案并通知乙方。乙方应在接到通知后第一时间赶到学校或指定医院。',
        '2. 若医疗机构建议学生需住院治疗或居家休养，乙方应积极配合办理请假或休学手续。',
        '3. 学生申请复学时，乙方须向学校提供正规医疗机构出具的“具备复学条件”的医学证明，经学校心理危机干预小组评估通过后方可复学。复学后，乙方仍需按学校要求定期反馈学生恢复情况。',
        '',
        '四、 附则',
        '1. 本协议一式两份，甲乙双方各执一份，自双方签字（盖章）之日起生效。',
        '2. 本协议未尽事宜，由甲乙双方另行协商解决。',
        '',
        '甲方代表（班主任/心理老师）签字：_________________',
        '联系电话：_________________',
        '',
        '乙方（学生监护人）签字：_________________',
        '联系电话：_________________',
        '日期：_______年____月____日'
    ]

    for p_text in content_paragraphs:
        p = doc.add_paragraph(p_text)
        p.paragraph_format.first_line_indent = Pt(24) # 首行缩进两字符
        for run in p.runs:
            run.font.name = u'宋体'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), u'宋体')
            run.font.size = Pt(12)

    # 将文档保存到内存中
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name=f"{sid}_家校心理安全协议.docx",
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )

# ==================== 启动服务 ====================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    print(f"服务正在启动，监听端口: {port}")
    app.run(host='0.0.0.0', port=port)
