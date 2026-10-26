"""Small, inspectable Chinese query rules; no model call or benchmark data dependency.

These are conservative field constraints, not general natural-language inference.
A nearby topic is insufficient evidence for a requested phone number, price or result.
"""

import re

# (question wording, necessary evidence wording). Multiple requested fields must all match.
FIELDS = (
    (r"颜色|色彩", r"色"),
    (r"生日|诞辰", r"生日|出生"),
    (r"(?:哪|什么).{0,3}(?:酒店|旅馆)|住的.{0,3}(?:酒店|旅馆)", r"酒店|旅馆|宾馆|民宿"),
    (r"车次|公交车号|几路(?:公交|车)", r"车次|[0-9一二三四五六七八九十]+路|[GDZTK]\d+"),
    (r"车票.*谁买|谁.*买.*车票", r"买.{0,8}车票|车票.{0,8}(?:买|购买)"),
    (r"天气|下雨|下雪", r"天气|下雨|下雪|晴天|阴天|多云"),
    (r"哪家店.*吃|在哪.*吃的", r"餐厅|饭店|餐馆|食堂|小吃店"),
    (
        r"多少[钱元]|花了多少|工资|薪水|学费|费用|票价",
        r"[0-9一二三四五六七八九十百千万]+元|工资|薪水|月薪|费用|学费|票价",
    ),
    (r"厂长|经理叫什么", r"厂长|经理"),
    (r"哪位同事|同事.*谁", r"同事"),
    (r"住在我隔壁|住我隔壁", r"隔壁|邻居"),
    (r"打卡|几点.*上班", r"打卡|[点时].{0,6}上班|上班.{0,6}[点时]"),
    (r"电话(?:号码)?|手机号码", r"电话|手机号码|通话"),
    (r"打电话|通话", r"打电话|通话"),
    (r"班主任", r"班主任"),
    (r"哪家医院|哪个医院|哪所医院", r"医院|卫生院|诊所"),
    (r"哪款手机|手机.*(?:型号|品牌)", r"手机|iPhone|华为|小米|OPPO|vivo"),
    (r"心率", r"心率|心跳"),
    (r"打鼾|鼾声", r"打鼾|鼾声"),
    (r"(?:第一位|哪位|谁是).{0,4}老师|老师叫什么", r"老师|师傅|师父"),
    (r"相机.*品牌|哪个品牌", r"品牌|佳能|尼康|索尼|富士|徕卡"),
    (r"面积|平方米", r"面积|平方米|平米|㎡"),
    (r"门牌|几号(?:门|楼)", r"\d+号|门牌.{0,8}\d"),
    (r"摊主|谁.*收.*款", r"摊主|收款"),
    (r"主持人|谁.*主持", r"主持"),
    (r"带队", r"带队|领队"),
    (r"实际用过.*药|用过哪种药", r"(?:服|吃|用).{0,8}(?:药|青霉素|磺胺)"),
    (r"血压", r"血压|mmHg"),
    (r"血型", r"血型|[ABO]+型"),
    (r"合同.*到期", r"合同|租期"),
    (r"搬家|搬去", r"搬家|搬去|迁居"),
    (r"主诊医生", r"医生|医师"),
    (r"第一次.*过敏.*(?:几月|哪天)", r"第一次.{0,20}过敏|过敏.{0,20}\d+月\d+[日号]"),
    (r"午休|午睡|中午.{0,6}睡|午间休息", r"午休|午睡|中午.{0,8}睡"),
    (r"摄影|拍照|相机|镜头", r"摄影|拍照|拍摄|相机|拍.{0,5}(?:花|鸟|景)"),
    (r"养什么花|栽哪.{0,3}花", r"花|月季|茉莉|牡丹|芍药|杜鹃"),
    (r"吃.{0,5}(?:什么|哪道|哪种)|主菜|[早午晚](?:饭|餐)", r"吃|用餐|[早午晚](?:饭|餐)|喝粥"),
)

EXPANSIONS = (
    (r"摄影|拍照|相机|镜头", ("摄影", "拍照", "拍")),
    (r"午休|午睡|中午.{0,6}睡|午间休息", ("午休", "午睡")),
    (r"诞辰", ("生日",)),
    (r"乐器", ("二胡", "笛子", "钢琴", "口琴", "吉他", "小提琴")),
)

RELATIVES = "女儿|儿子|孙女|孙子|老伴|侄女|侄子|舅舅|姨妈|堂弟|堂姐|姐姐|哥哥|弟弟|妹妹|宠物猫"
NAME = re.compile(
    rf"(?:{RELATIVES})([\u4e00-\u9fff]{{2,3}}?)"
    r"(?=的|生日|过生日|哪天|是|在|平时|喜欢|从事|电话|还|去|同去|同行|一起|选)"
)
TITLED_NAME = re.compile(r"([\u4e00-\u9fff](?:阿姨|叔叔))")
COMPANION = re.compile(r"(?:和|与|陪)([\u4e00-\u9fff]{2,3}?)(?=去|游|一起|同行|在)")
NAMED_COMPANION = re.compile(
    r"(?:^|[，,、]|找找|同学|姐姐|哥哥)([\u4e00-\u9fff]{2,3}?)(?=同行|一起去|同去)"
)
SHORT_NAME = re.compile(r"(小[\u4e00-\u9fff])(?=去|的|同|一起|最|选|从|是|在|还|班|电话|生日)")
VENUE = re.compile(
    r"(?:在|去|到)([\u4e00-\u9fff]{2,12}?(?:书屋|服务站|图书馆|公园|步道|菜市场|文化馆|医院|小区))"
)
SCOPES = (
    "鹦鹉",
    "钱包",
    "盆栽",
    "名单",
    "备忘卡",
    "临时住处",
    "收藏清单",
    "曲目",
    "二胡",
    "笛子",
    "青霉素",
    "磺胺",
)


def evidence_constraints(question):
    patterns = [evidence for wording, evidence in FIELDS if re.search(wording, question)]
    scopes = [
        *NAME.findall(question),
        *TITLED_NAME.findall(question),
        *COMPANION.findall(question),
        *SHORT_NAME.findall(question),
    ]
    scopes += [
        name for name in NAMED_COMPANION.findall(question) if not re.search(r"我|你|他|她", name)
    ]
    scopes += [term for term in SCOPES if term in question]
    scopes += [name for name in VENUE.findall(question) if not re.search(r"哪|什么|一家", name)]
    scopes += re.findall(r"《([^》]{1,80})》", question)
    return patterns, list(dict.fromkeys(scopes))


def expanded_terms(question):
    return list(
        dict.fromkeys(
            term for wording, terms in EXPANSIONS if re.search(wording, question) for term in terms
        )
    )


def supports_requested_fields(question, text):
    patterns, scopes = evidence_constraints(question)
    return all(re.search(pattern, text, re.I) for pattern in patterns) and all(
        scope in text for scope in scopes
    )
