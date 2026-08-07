"""規則過濾 + 議題標籤 + 發言人分類（規則層；LLM 層由 Claude 喺 review 時補）。"""
import re

# --- 議題標籤規則（對應 deck 嘅 issue taxonomy）---
LABEL_PATTERNS = {
    "two-day-format": r"兩日|兩天|分開兩|分兩|2日|two[- ]day|星期六.*星期日|周六.*周日",
    "guaranteed-quota": r"保證(購買|名額)|出席率|跑班|訓練班|課程.*名額",
    "charity-quota": r"慈善|charity|NGO|善款",
    "dual-identity": r"雙重|兩本護照|兩個身份|bno|回鄉證|兩次抽籤|重複報名",
    "insider-channel": r"有方法|勢力人士|識人|內部|特權|天龍|走後門",
    "resale-blackmarket": r"小紅書|炒(位|飛)|黑市|賣(位|bib)|代跑|直通位",
    "quota-general": r"名額|quota|抽唔中|中籤|抽籤|落選|配額",
    "ballot-odds": r"中籤率|抽中率|難抽|抽足|年年都唔中",
    "road-closure": r"封路|擾民|塞車|改道|交通",
    "north-metropolis": r"北都|北部都會",
    "route-change": r"賽道|路線|啟德|中九龍|西隧|三橋三隧|維園",
    "medical-safety": r"受傷|送院|暈|急救|醫療|危殆|安全",
    "fees": r"報名費|加價|貴|收費|\$\d{3}",
    "platinum-label-comparison": r"白金標|金標|大滿貫|港珠澳|深圳馬|廣州馬|東京馬|倫敦馬",
    "mega-event-economy": r"盛事|經濟效益|旅遊|小店|遊客",
    "runner-pack-expo": r"跑手包|選手包|expo|博覽",
    "weather": r"天氣|落雨|紅雨|酷熱|氣溫",
    "banned-shoes": r"禁鞋|banned shoe|prime x|超級鞋|厚底",
    "bank-noise": r"活期|存款|息口|派息|利率|信用卡|里數",
}

RUNNER_SIGNALS = r"我(跑|報|抽|練)|自己跑|完賽|PB|pb|sub ?\d|配速|長課|LSD|interval|跑班|跑會|全馬|半馬|10[Kk]|訓練|操練|中籤|抽唔中|跑手包"
SPECTATOR_SIGNALS = r"擾民|阻住|封路.*返工|唔跑|打卡|搵錢|cap水|賺錢"


def label_text(text):
    t = text or ""
    out = [lab for lab, pat in LABEL_PATTERNS.items() if re.search(pat, t, re.I)]
    return out or ["other"]


# 明確講緊渣馬 —— 呢啲詞單獨出現已經算命中
SCHKM_STRONG = r"渣馬|渣打.{0,4}馬拉松|香港馬拉松|SCHKM|schkm|hkmarathon"

# 香港語境訊號 —— 「馬拉松」呢個泛詞要配埋呢啲先算數
HK_CONTEXT = (
    r"香港|港島|九龍|新界|維園|維多利亞公園|尖沙咀|銅鑼灣|啟德|西隧|東隧|紅隧"
    r"|東區走廊|彌敦道|中九龍|北都|北部都會|田總|田徑總會|港鐵|旺角|灣仔"
    r"|街馬|港珠澳|大尾篤|吐露港|沙田|將軍澳"
    # 香港制度／賽事專有語 —— 台灣唔會用
    r"|屬會|慈善位|達標跑手|三橋三隧|抽唔中|中籤率"
)

# 粵語書面語助詞 —— 最有效嘅港台判別器。
# 台灣同樣用繁體，但唔會寫「嘅／咗／唔／喺／嗰／咁樣／乜」。
# 命中 2 個或以上即視為香港語境。
CANTONESE_MARKERS = [
    "嘅", "咗", "唔", "喺", "嗰", "咁", "乜", "嘢", "係咪", "啲", "冇", "梗係", "睇",
]


def _is_cantonese(t, threshold=2):
    return sum(1 for m in CANTONESE_MARKERS if m in t) >= threshold

# 其他地區賽事 —— 冇香港訊號就當離題
OTHER_REGION = (
    r"台北馬|臺北馬|彰化|台南|臺南|高雄|花蓮|日月潭|萬金石"
    r"|東京馬|大阪馬|名古屋|福井|札幌|金澤"
    r"|首爾|曼谷|吉隆坡|新加坡馬|柏林馬|芝加哥馬|紐約馬|波士頓馬|倫敦馬"
    r"|重慶馬|廣州馬|深圳馬|上海馬|北京馬|廈門馬"
)


# 賽事領域詞 —— 留言通常唔會重複「馬拉松」三個字，靠呢啲識別
RACE_DOMAIN = (
    r"半馬|全馬|10\s?[Kk]|5\s?[Kk]|賽道|路線|封路|抽籤|中籤|抽唔中|名額|quota"
    r"|報名|跑手|跑友|跑班|跑會|田總|田徑總會|慈善位|達標|起跑|完賽|終點|水站"
    r"|選手包|跑手包|分兩日|兩日搞|breakfast run|pacer|配速"
)


# 金融產品語境 —— 命中即當理財帖，唔理有冇「渣打馬拉松」字眼
FINANCE_CONTEXT = (
    r"存款|活期|定期|年利率|利率|息口|派息|高息|新資金|本金|債券|信用卡|里數"
    r"|迎新|回贈|rebate|年費|轉數快|FPS|戶口|分行|理財|投資|保本"
    # 虛擬銀行/理財產品品牌 —— 「做Mox好過渣馬」呢類比較帖走呢條
    r"|Mox|WeLab|ZA ?Bank|livi|Flexiboost|富融|平安[一壹]賬通|螞蟻|天星"
)

# 明確參賽行為 —— 用嚟推翻金融誤判（例：「跑完渣馬去銀行開戶」）
RACE_PARTICIPATION = (
    r"我(跑|報名|抽|練|完成)|參賽|完賽|中籤|抽唔中|起跑|賽道|跑手包|選手包"
    r"|配速|PB|pb|sub ?\d|練習|訓練|操練"
)


# 「馬拉松」作為比喻 —— 教育/人生/工作馬拉松，唔關賽事事
METAPHOR = (
    r"(教育|人生|工作|職場|創業|讀書|補習|考試|呈分試|減肥|育兒|投資|追劇|開會)"
    r"[^。！？]{0,12}馬拉松"
)

# 其他香港賽事 —— 保留（本地跑步生態背景）但降級為 background
OTHER_HK_RACE = (
    r"Garmin Run|街馬|香港街馬|毅行者|Pegasus|天水圍.{0,4}錦標|新鴻基.{0,6}錦標"
    r"|UTMB|越野|trail|北都馬拉松|港珠澳.{0,4}半馬|大尾篤"
)


def is_metaphor(text):
    t = text or ""
    if not re.search(METAPHOR, t):
        return False
    # 有實際賽事語言就唔算比喻
    return not re.search(RACE_DOMAIN, t, re.I)


def is_other_hk_race(text):
    """香港其他賽事：保留做背景，但唔應該混入渣馬 direct/adjacent 組。"""
    t = text or ""
    if re.search(SCHKM_STRONG, t):
        return False
    return bool(re.search(OTHER_HK_RACE, t, re.I))


def is_noise(text, cfg, is_comment=False):
    """True = 應剔往噪音線。

    留言（is_comment=True）語境由母帖界定，只做金融過濾。

    帖文核心原則：**呢個係香港賽事監察，必須有香港語境或明確渣馬字眼。**

      1. 金融產品語境 + 冇明確參賽行為 → 剔（渣打「馬拉松活期存款」走呢條）
      2. 離題詞（賽馬/河馬等）+ 冇跑步訊號 → 剔
      3. SCHKM 強訊號（渣馬／渣打馬拉松／香港馬拉松）→ 保留
      4. 其餘：必須「有香港語境」AND「有賽事語言」→ 否則剔
         （擋走台灣/日本等純外地跑步帖，佢哋有半馬/馬拉松但冇香港訊號）
    """
    t = text or ""
    nf = cfg.get("noise_filters", {})
    finance = bool(re.search(FINANCE_CONTEXT, t, re.I))
    participation = bool(re.search(RACE_PARTICIPATION, t))

    # 1. 金融產品帖：即使有「渣打馬拉松」字眼都剔
    if finance and not participation:
        return True

    # 2. 離題詞 + 比喻用法
    off = any(w in t for w in nf.get("offtopic_terms", []))
    if off and not participation:
        return True
    if is_metaphor(t):
        return True

    if is_comment:
        return False

    strong = bool(re.search(SCHKM_STRONG, t))
    # 香港語境 = 地名/制度詞 或 粵語書面語
    hk = bool(re.search(HK_CONTEXT, t)) or _is_cantonese(t)
    other_region = bool(re.search(OTHER_REGION, t))
    domain = bool(re.search(RACE_DOMAIN, t, re.I))
    generic = bool(re.search(r"馬拉松|路跑", t))

    # 3. 明確講渣馬
    if strong:
        return False

    # 4. 其餘一律要求香港語境 + 賽事語言
    #    （其他香港賽事名本身就係賽事訊號，例：「街馬」冇「馬拉松」三個字）
    hk_race = bool(re.search(OTHER_HK_RACE, t, re.I))
    if not hk:
        return True
    if other_region and not (domain or hk_race):
        return True
    return not (domain or generic or hk_race)


def is_bank_line(text):
    t = text or ""
    return bool(re.search(r"活期|存款|息口|派息|利率", t)) and not re.search(
        RUNNER_SIGNALS, t
    )


def speaker_type(text):
    """跑手 / 花生 / 未判 —— 規則初判，人手核對時可改。"""
    t = text or ""
    r = bool(re.search(RUNNER_SIGNALS, t))
    s = bool(re.search(SPECTATOR_SIGNALS, t))
    if r and not s:
        return "runner"
    if r and s:
        return "runner-likely"
    if s:
        return "spectator"
    return "unclassified"


def relevance(text):
    # 其他香港賽事：保留做本地跑步生態背景，唔混入渣馬議題組
    if is_other_hk_race(text):
        return "background"

    labs = label_text(text)
    direct = {
        "two-day-format",
        "guaranteed-quota",
        "dual-identity",
        "insider-channel",
        "quota-general",
        "ballot-odds",
        "charity-quota",
    }
    strong = bool(re.search(SCHKM_STRONG, text or ""))
    if set(labs) & direct:
        # 議題詞命中，但如果連渣馬字眼都冇，只算 adjacent
        return "direct" if strong else "adjacent"
    if labs != ["other"]:
        return "adjacent" if strong else "background"
    return "background"
