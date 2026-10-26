"""Author/freeze the independent v1 benchmark; never overwrite a different suite."""

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests/memory_eval/fixtures/suite-v1.json"

PROFILES = {
    "A": {
        "child": "孙女小禾",
        "child_short": "小禾",
        "trip_city": "苏州",
        "trip_year": "2019",
        "friend": "周敏",
        "sea_city": "厦门",
        "sea_day": "2021年5月4日",
        "sister": "林兰",
        "old_city": "青岛",
        "old_year": "2008",
        "job": "电工",
        "job_city": "杭州",
        "job_years": "三年",
        "neighbor": "王阿姨",
        "flower": "兰花",
        "niece": "侄女小雪",
        "profession": "小学老师",
        "color": "紫色",
        "son": "女儿小晴",
        "birthday": "3月15日",
        "partner": "老伴李婉",
        "partner_day": "7月8日",
        "morning": "七点",
        "nap": "三十分钟",
        "instrument": "二胡",
        "subject": "荷花",
        "address": "静安路18号",
        "market": "南门菜市场",
        "bought": "花盆",
        "venue": "竹影书屋",
        "reading_day": "2022年5月20日",
        "station": "春桥服务站",
        "volunteer_day": "2024年3月12日",
        "allergy": "青霉素",
        "month": "8月",
        "skill": "篆刻",
        "scene": "白鹭公园",
        "unknown_person": "堂弟海星",
        "unknown_cat": "小墨",
        "club": "晨光棋社",
        "bird": "团团",
        "book": "山海小札",
        "uncle": "舅舅顾森",
        "wallet": "深蓝色",
        "plant": "阳台东角",
    },
    "B": {
        "child": "孙子小川",
        "child_short": "小川",
        "trip_city": "厦门",
        "trip_year": "2017",
        "friend": "许涛",
        "sea_city": "南京",
        "sea_day": "2020年9月6日",
        "sister": "沈华",
        "old_city": "昆明",
        "old_year": "2011",
        "job": "印刷工",
        "job_city": "宁波",
        "job_years": "四年",
        "neighbor": "郑叔叔",
        "flower": "月季",
        "niece": "侄子小哲",
        "profession": "工程师",
        "color": "橙色",
        "son": "儿子小远",
        "birthday": "11月22日",
        "partner": "老伴陈秋",
        "partner_day": "5月6日",
        "morning": "六点半",
        "nap": "四十五分钟",
        "instrument": "笛子",
        "subject": "飞鸟",
        "address": "松涛街26号",
        "market": "北桥菜市场",
        "bought": "绳子",
        "venue": "山水书屋",
        "reading_day": "2023年4月16日",
        "station": "海湾服务站",
        "volunteer_day": "2024年11月3日",
        "allergy": "磺胺",
        "month": "6月",
        "skill": "木雕",
        "scene": "松林步道",
        "unknown_person": "表弟青岚",
        "unknown_cat": "阿绒",
        "club": "海风棋社",
        "bird": "圆圆",
        "book": "秋水随笔",
        "uncle": "舅舅陶林",
        "wallet": "浅绿色",
        "plant": "北窗台",
    },
}

# Closed answers and question wording are authored independently of retrieval results.
# slug, kind, key, raw statement, time expression, required answer groups, four questions.
NORMAL = [
    (
        "trip",
        "travel",
        "{trip_city}",
        "{trip_year}年我陪{child}去{trip_city}旅游",
        "{trip_year}年",
        [["{trip_year}"]],
        [
            "陪{child_short}去{trip_city}旅游是哪一年",
            "和{child_short}逛{trip_city}的那趟是几几年",
            "你还记得我带{child_short}游{trip_city}的年份吗",
            "回想一下，{child_short}同行的{trip_city}之旅发生在哪年",
        ],
    ),
    (
        "sea",
        "travel",
        "{friend}",
        "{sea_day}我和老同学{friend}去了{sea_city}",
        "{sea_day}",
        [["{sea_day}"]],
        [
            "我和{friend}去{sea_city}是哪天",
            "与老同学{friend}同游{sea_city}的日期是什么",
            "帮我找找{friend}一起去{sea_city}的日子",
            "那次与{friend}结伴到{sea_city}具体是哪天",
        ],
    ),
    (
        "sister",
        "travel",
        "{sister}",
        "{old_year}年我和姐姐{sister}去过{old_city}",
        "{old_year}年",
        [["{old_year}"]],
        [
            "与姐姐{sister}去{old_city}是哪年",
            "我陪{sister}游{old_city}在几几年",
            "姐姐{sister}同去{old_city}的年份你还记得吗",
            "翻翻旧事，{sister}同行的{old_city}旅行发生在哪年",
        ],
    ),
    (
        "job",
        "work",
        "{job_city}",
        "退休前我在{job_city}做{job}，工作过{job_years}",
        "",
        [["{job_city}"], ["{job_years}"]],
        [
            "退休前我做{job}在哪座城，做了几年",
            "我退休前当{job}时在哪座城市上过几年班",
            "能找回退休前那份{job}工作的地点和年限吗",
            "回顾当{job}那段工龄，退休前在哪儿干了多久",
        ],
    ),
    (
        "neighbor",
        "relationship",
        "{neighbor}",
        "隔壁的{neighbor}最爱养{flower}",
        "",
        [["{flower}"]],
        [
            "隔壁{neighbor}最爱养什么花",
            "{neighbor}喜欢栽哪一种花",
            "记得邻居{neighbor}的养花偏好吗",
            "我提过{neighbor}偏爱哪种花卉",
        ],
    ),
    (
        "niece",
        "relationship",
        "{niece}",
        "我的{niece}现在是一名{profession}",
        "",
        [["{profession}"]],
        [
            "{niece}从事什么职业",
            "我说{niece}是做哪一行的",
            "帮我回忆{niece}的工作身份",
            "家人{niece}的职业记下来了吗",
        ],
    ),
    (
        "color",
        "relationship",
        "{child}",
        "我的{child}最喜欢{color}",
        "",
        [["{color}"]],
        [
            "{child_short}最喜欢哪种颜色",
            "{child}偏爱的颜色是什么",
            "给{child_short}选东西该记住哪种颜色偏好",
            "我说过{child_short}最爱的色彩是哪种",
        ],
    ),
    (
        "birthday",
        "date",
        "{son}",
        "我的{son}生日是每年{birthday}",
        "",
        [["{birthday}"]],
        [
            "{son}的生日是几月几日",
            "给{son}过生日要记住哪个日子",
            "我记过{son}每年的诞辰吗，在哪天",
            "想查{son}生日的月份和日期",
        ],
    ),
    (
        "partner",
        "date",
        "{partner}",
        "{partner}的生日是每年{partner_day}",
        "",
        [["{partner_day}"]],
        [
            "{partner}生日是哪天",
            "每年哪天给{partner}庆生",
            "帮我找找{partner}的生日日期",
            "{partner}过生日的日子你记得吗",
        ],
    ),
    (
        "morning",
        "habit",
        "晨练",
        "我每天早上{morning}开始晨练，通常沿{scene}散步",
        "",
        [["{morning}"]],
        [
            "我在{scene}每天几点开始晨练",
            "平时早上沿{scene}锻炼是什么时刻开始",
            "记得我去{scene}晨练的开始时间吗",
            "沿{scene}那项清晨锻炼通常几点启动",
        ],
    ),
    (
        "nap",
        "habit",
        "午休",
        "我的午休通常持续{nap}，醒来会泡一杯温水",
        "",
        [["{nap}"]],
        [
            "我的午休一般有多长",
            "我中午习惯睡多久才起",
            "能找回我说过的午间休息时长吗",
            "我那段午睡通常持续多少时间",
        ],
    ),
    (
        "instrument",
        "interest",
        "{instrument}",
        "退休后我最爱练{instrument}，每次都会坐在窗边",
        "",
        [["{instrument}"]],
        [
            "我退休后最爱练哪种乐器",
            "窗边练习的那件乐器叫什么",
            "记得退休后我偏爱的乐器吗",
            "我退休后常在窗边练的是什么乐器",
        ],
    ),
    (
        "photo",
        "interest",
        "摄影",
        "我做摄影时最喜欢拍{subject}，不会用这条记录说明任何一次实际出游",
        "",
        [["{subject}"]],
        [
            "我的摄影最喜欢拍什么题材",
            "拿相机时我最爱捕捉什么对象",
            "我以前说过拍照偏好哪种景物",
            "摄影这项爱好里我最偏爱什么主题",
        ],
    ),
    (
        "home",
        "place",
        "住址",
        "我家的住址是{address}，这是我明确确认过的当前地址",
        "",
        [["{address}"]],
        [
            "我现在住在哪个地址",
            "我家的住址是哪里",
            "帮我找一下明确确认过的当前住处",
            "当前家里那处地址记录是什么",
        ],
    ),
    (
        "market",
        "place",
        "{market}",
        "2025年6月18日中午我去了{market}买{bought}",
        "2025年6月18日",
        [["{market}"]],
        [
            "2025年6月18日中午我在哪里买{bought}",
            "去年6月18日中午买{bought}去的是哪处市场",
            "能找回那天中午买{bought}的{market}经历吗",
            "我买{bought}的那次六月十八日去了哪",
        ],
    ),
    (
        "reading",
        "event",
        "{venue}",
        "{reading_day}我在{venue}参加过读书会",
        "{reading_day}",
        [["{reading_day}"]],
        [
            "在{venue}参加读书会是哪天",
            "{venue}那场书友聚会的日期是什么",
            "你能找回我参加{venue}读书会的日子吗",
            "回顾{venue}的读书活动，具体是哪一天",
        ],
    ),
    (
        "volunteer",
        "event",
        "{station}",
        "{volunteer_day}我到{station}做志愿服务",
        "{volunteer_day}",
        [["{volunteer_day}"]],
        [
            "我去{station}做志愿服务是哪天",
            "{station}那次义工活动发生在什么日期",
            "帮我找回到{station}帮忙的日子",
            "在{station}服务的那一天是什么时候",
        ],
    ),
    (
        "allergy",
        "health",
        "过敏",
        "我明确说过自己对{allergy}过敏，这只是合成的个人陈述，不是医疗诊断",
        "",
        [["{allergy}"]],
        [
            "我说自己对哪种药过敏",
            "我明确提过的药物过敏对象是什么",
            "我的过敏陈述涉及哪种药物",
            "我曾亲口说过对什么药物有过敏反应",
        ],
    ),
    (
        "checkup",
        "health",
        "体检",
        "我的年度体检固定安排在每年{month}",
        "",
        [["{month}"]],
        [
            "我的年度体检固定在哪个月",
            "我一年一度的检查安排在什么月份",
            "我提过年度身体检查的月份吗",
            "那项每年的健康检查定在几月",
        ],
    ),
    (
        "skill",
        "interest",
        "想学",
        "退休以后我最想学的手艺是{skill}",
        "",
        [["{skill}"]],
        [
            "退休以后我最想学什么手艺",
            "我退休后那项想学的技能是什么",
            "能想起我说最想学的手艺吗",
            "退下来后我希望学会哪种手艺",
        ],
    ),
]


def fill(value, profile):
    if isinstance(value, str):
        return value.format(**profile)
    return [fill(item, profile) for item in value]


def build():
    facts, questions = [], []

    def fact(actor, slug, kind, key, text, when="", action="normal", **extra):
        identifier = f"{actor}.{slug}"
        facts.append(
            dict(
                id=identifier,
                actor=actor,
                kind=kind,
                key=key,
                text="【Synthetic】" + text,
                time_expression=when,
                action=action,
                **extra,
            )
        )
        return identifier

    def question(actor, group, text, expected=(), answers=(), **extra):
        questions.append(
            dict(
                id=f"Q{len(questions) + 1:03}",
                actor=actor,
                group=group,
                text=text.rstrip("？?。") + "？",
                expected=list(expected),
                answer_groups=list(answers),
                **extra,
            )
        )

    normal_questions = {}
    for actor, p in PROFILES.items():
        for index, definition in enumerate(NORMAL):
            slug, kind, key, text, when, answers, prompts = fill(list(definition), p)
            recorded = f"{2016 + index % 8}-11-01T12:00:00"
            if when:
                parts = [int(v) for v in re.findall(r"\d+", when)]
                if len(parts) == 3:
                    recorded = (datetime(*parts) + timedelta(days=1)).isoformat()
                elif len(parts) == 1:
                    recorded = f"{parts[0]}-11-01T12:00:00"
            identifier = fact(
                actor,
                slug,
                kind,
                key,
                text,
                when,
                recorded_at=recorded,
            )
            normal_questions[identifier] = prompts
            for group, prompt in zip(
                ("exact", "semantic", "cross_session"), prompts[:3], strict=True
            ):
                question(actor, group, prompt, [identifier], answers)
            if index < 5:
                question(actor, "performance", prompts[3], [identifier], answers)
        for index, body in enumerate(("膝盖", "肩膀", "脚踝", "手腕", "腰")):
            old = fact(
                actor,
                f"injury_{index}",
                "health",
                body,
                f"我的{body}在{p['scene']}活动时受伤了",
                action="health_before",
                recorded_at="2026-10-24T12:00:00",
            )
            new = fact(
                actor,
                f"recovered_{index}",
                "health",
                body,
                f"我的{body}在{p['scene']}那次活动后现在已经好了",
                action="health_after",
                recorded_at=f"2026-10-26T12:0{index}:00",
                supersedes=old,
            )
            for prompt in (
                f"我在{p['scene']}伤的{body}现在怎么样",
                f"{p['scene']}那次{body}的最新恢复状态是什么",
            ):
                question(
                    actor,
                    "conflict",
                    prompt,
                    [new],
                    [["已经好了", "恢复", "康复"]],
                    forbidden=[old],
                )
        edits = [
            (
                "mail",
                "place",
                "通讯地址",
                "红叶路7号",
                "翠竹路9号" if actor == "A" else "梧桐巷12号",
            ),
            (
                "opera",
                "interest",
                "喜欢的戏曲",
                "京剧",
                "评弹" if actor == "A" else "越剧",
            ),
            (
                "walk",
                "habit",
                "散步时间",
                "上午十点",
                "下午五点" if actor == "A" else "傍晚六点",
            ),
            (
                "retire",
                "date",
                "退休年份",
                "1995年",
                "2000年" if actor == "A" else "2002年",
            ),
            (
                "name",
                "relationship",
                "常用称呼",
                "老赵",
                "陈师傅" if actor == "A" else "周老师",
            ),
        ]
        for index, (slug, kind, key, before, after) in enumerate(edits):
            text = f"我明确确认的{key}是{before}"
            changed = f"我已经亲自更正，{key}应当是{after}"
            identifier = fact(
                actor,
                "edited_" + slug,
                kind,
                key,
                text,
                action="edit",
                corrected_text="【Synthetic】" + changed,
                recorded_at=f"201{index}-07-01T12:00:00",
            )
            for prompt in (
                f"我亲自更正后的{key}是什么",
                f"请按用户修改记录告诉我最新的{key}",
            ):
                question(
                    actor,
                    "conflict",
                    prompt,
                    [identifier],
                    [[after]],
                    expected_origin="user_edit",
                )
        historical = [
            (
                "factory",
                "work",
                "旧港工厂" if actor == "A" else "青原车间",
                "维修电机" if actor == "A" else "装订书册",
            ),
            (
                "journey",
                "travel",
                "吴桥古镇" if actor == "A" else "柳溪古镇",
                "看过石拱桥" if actor == "A" else "参观过瓷窑",
            ),
            ("old_home", "place", "旧居", "雨花巷3号" if actor == "A" else "听竹街5号"),
            (
                "old_hobby",
                "habit",
                "过去的晨间活动",
                "慢跑" if actor == "A" else "练剑",
            ),
            ("festival", "event", "那次灯会", "看花灯" if actor == "A" else "猜灯谜"),
        ]
        for index, (slug, kind, key, value) in enumerate(historical):
            identifier = fact(
                actor,
                "historical_" + slug,
                kind,
                key,
                f"以前那段关于{key}的经历，我当时{value}",
                action="historical",
                recorded_at=f"200{index}-05-01T12:00:00",
            )
            question(
                actor,
                "performance",
                f"我以前关于{key}那段经历，具体做过或记过什么",
                [identifier],
                [[value]],
            )
        deleted = [
            (
                "bird",
                "interest",
                "鹦鹉",
                f"我养的鹦鹉名字是{p['bird']}",
                "我的鹦鹉叫什么名字",
                "那只鹦鹉的名字还记得吗",
            ),
            (
                "book",
                "interest",
                p["book"],
                f"我借过《{p['book']}》这本书",
                f"我借过《{p['book']}》吗",
                f"能查到我借《{p['book']}》的经历吗",
            ),
            (
                "uncle",
                "date",
                p["uncle"],
                f"{p['uncle']}的生日是2月3日",
                f"{p['uncle']}的生日是哪天",
                f"我记过{p['uncle']}哪天过生日吗",
            ),
            (
                "wallet",
                "event",
                "丢失的钱包",
                f"我曾丢失的钱包是{p['wallet']}",
                "我丢失的钱包是什么颜色",
                "丢的那只钱包的颜色是什么",
            ),
            (
                "plant",
                "place",
                "小橘盆栽",
                f"我的小橘盆栽放在{p['plant']}",
                "小橘盆栽被我放在哪个位置",
                "能找回小橘盆栽的摆放位置吗",
            ),
        ]
        for slug, kind, key, text, q1, q2 in deleted:
            identifier = fact(
                actor,
                "deleted_" + slug,
                kind,
                key,
                text,
                action="delete",
                recorded_at="2024-07-01T12:00:00",
            )
            for prompt in (q1, q2):
                question(actor, "deleted", prompt, forbidden=[identifier])
        invalid = [
            ("inactive", "event", p["club"], f"我加入过{p['club']}的通知名单"),
            ("permission", "health", "体质备忘卡", f"我的体质备忘卡写着{p['allergy']}"),
            ("expired", "place", "临时住处", f"我的临时住处曾在{p['scene']}旁的客舍"),
            (
                "future",
                "event",
                "收藏清单",
                f"我的收藏清单未来才开始生效，包含{p['skill']}作品",
            ),
            (
                "untraceable",
                "interest",
                "无出处曲目",
                f"无出处曲目是{p['instrument']}小调",
            ),
        ]
        for action, kind, key, text in invalid:
            fact(
                actor,
                "invalid_" + action,
                kind,
                key,
                text,
                action=action,
                recorded_at="2023-07-01T12:00:00",
            )
        unknown = [
            "我去年6月18日中午吃了什么",
            "2025年6月18日晚上我吃过哪道主菜",
            f"我上周五在哪家医院做了核磁检查，和{p['scene']}有关吗",
            f"宠物猫{p['unknown_cat']}的生日是几月几号",
            f"我在从没提过的安岚镇住的旅馆叫什么，{p['child_short']}去过吗",
            f"我的血型记下来了吗，{p['partner']}是否知道",
            f"{p['unknown_person']}的电话号码是多少",
            f"我签过的住房合同哪天到期，和{p['address']}有关吗",
            f"{p['neighbor']}是不是已经搬家了，搬去哪儿",
            f"我昨天傍晚有没有给{p['child_short']}打电话",
        ]
        for prompt in unknown:
            question(actor, "unknown", prompt)
    # Other actor's specific entities: no answer is authorized for the querying user.
    for actor in PROFILES:
        other = "B" if actor == "A" else "A"
        for slug in (
            "trip",
            "sea",
            "sister",
            "neighbor",
            "niece",
            "color",
            "birthday",
            "partner",
            "reading",
            "volunteer",
        ):
            question(
                actor,
                "isolation",
                normal_questions[f"{other}.{slug}"][0],
                forbidden=[f"{other}.{slug}"],
            )
    # Missing attributes of known people/events are harder than unrelated random
    # unknowns. Keep them in the suite so topical evidence cannot count as an answer.
    for actor, p in PROFILES.items():
        details = [
            f"陪{p['child_short']}去{p['trip_city']}那趟住的是哪家酒店",
            f"我带{p['child_short']}去{p['trip_city']}坐了哪个车次",
            f"{p['trip_city']}那次和{p['child_short']}同行的车票是谁买的",
            f"我和{p['friend']}游{p['sea_city']}那天具体是什么天气",
            f"与{p['friend']}在{p['sea_city']}旅行时我在哪家店吃的晚饭",
            f"姐姐{p['sister']}同行的{p['old_city']}之旅总共花了多少钱",
            f"退休前我做{p['job']}时每月工资是多少",
            f"我在{p['job_city']}当{p['job']}时厂长叫什么名字",
            f"当{p['job']}那段工作中，哪位同事住在我隔壁",
            f"退休前在{p['job_city']}上班每天几点打卡",
            f"{p['neighbor']}家具体是几号门牌",
            f"{p['niece']}的电话号码是多少",
            f"{p['child_short']}的班主任老师叫什么名字",
            f"{p['son']}是在哪家医院出生的",
            f"{p['partner']}平时用哪款手机",
            f"我在{p['scene']}晨练时平均心率具体是多少",
            f"我的午休有没有打鼾监测数据，{p['partner']}说过吗",
            f"我学{p['instrument']}的第一位老师叫什么",
            f"我拍{p['subject']}用的相机是哪个品牌",
            f"我想学{p['skill']}的课程学费是多少钱",
            f"我在{p['address']}那套房屋的面积是多少",
            f"{p['market']}那天是哪位摊主收的款",
            f"{p['venue']}那场读书会的主持人是谁",
            f"{p['station']}志愿活动是哪位老师带队的",
            f"我以前告诉过你的从家到{p['scene']}的公交车号是什么",
            f"我对{p['allergy']}过敏是在哪家医院诊断的",
            f"我第一次对{p['allergy']}过敏具体是几月几日",
            f"我在每年{p['month']}体检时的主诊医生叫什么名字",
            f"对{p['allergy']}过敏时我实际用过哪种药",
            f"我每年{p['month']}那份检查报告的具体血压读数是多少",
        ]
        for prompt in details:
            question(actor, "unknown_details", prompt)
        state_queries = [
            ("inactive", f"我目前还能使用的{p['club']}通知名单有记录吗"),
            ("permission", "仅针对我禁止AI使用的体质备忘卡，里面的原话是什么"),
            ("expired", "目前仍有效的临时住处在什么地方"),
            ("future", f"关于{p['skill']}的收藏清单，当前已经生效的内容是什么"),
            ("untraceable", f"我那条没有原文来源的{p['instrument']}曲目具体叫什么"),
        ]
        for action, prompt in state_queries:
            question(
                actor, "state_filter", prompt, forbidden=[f"{actor}.invalid_{action}"]
            )
    assert len(facts) == 100 and all(
        sum(f["actor"] == a for f in facts) == 50 for a in PROFILES
    )
    assert len(questions) == 310
    assert len({q["text"] for q in questions}) >= 200
    return {
        "version": "memory-eval/1",
        "synthetic": True,
        "reference_date": "2026-10-26",
        "facts": facts,
        "questions": questions,
        "targets": {
            "recall_at_5": 0.90,
            "top1_accuracy": 0.80,
            "conflict_accuracy": 0.95,
            "cross_user_leakage": 0,
            "deleted_recall": 0,
            "retrieval_p95_ms": 2000,
        },
        "grading": "Source IDs plus independent closed answer groups; no LLM self-grading.",
    }


def main():
    value = build()
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    sha = hashlib.sha256(raw).hexdigest()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        if TARGET.read_bytes() != raw:
            raise SystemExit("v1 is frozen; refusing to replace a different suite")
    else:
        with TARGET.open("xb") as file:
            file.write(raw)
    seal = TARGET.with_suffix(".sha256")
    if seal.exists() and seal.read_text().strip() != sha:
        raise SystemExit("Existing v1 seal mismatch")
    seal.write_text(sha + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "facts": len(value["facts"]),
                "questions": len(value["questions"]),
                "unique_questions": len({q["text"] for q in value["questions"]}),
                "sha256": sha,
            }
        )
    )


if __name__ == "__main__":
    main()
