# -*- coding: utf-8 -*-
"""SUZAKU 静的サイトジェネレータ。

使い方:
    python3 scripts/gen.py

- scripts/data_*.py の単一ソースデータから、製品/技術/OS/ニュースの各ページを生成
- src/pages/ 配下のフラグメント(本文のみのHTML)を共通レイアウトで包んで出力
- 製品画像・技術ビジュアルをSVGとして assets/img/ に生成
- クライアント用データ data/products.js、sitemap.xml、robots.txt を生成

Next.js移行時は、この出力ディレクトリ構造が app/ ルータのルートに1:1対応する。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_products import ALL_PRODUCTS, PHONES, TABLETS, ACCESSORIES, LINES, BIZ_PRODUCTS, BIZ_OS  # noqa: E402
from data_collab import COLLABS, COLLAB_SILICON, COLLAB_SOC_CLOCK, collab_by_slug  # noqa: E402
from data_tech import TECHS, OS_VERSIONS  # noqa: E402
from data_misc import NEWS, FAQ, HISTORY, GLOSSARY  # noqa: E402
from data_docs import DOCS  # noqa: E402
import svg_art  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "pages"
SITE_NAME = "SUZAKU(朱雀)"
BASE_URL = "https://suzaku.example.jp"


def _asset_version():
    """assets/css・assets/js・data_*.py(/data/products.js の生成元)の内容から
    短いハッシュを作り、キャッシュバスティング用のクエリ文字列(?v=...)に使う。
    CSS/JSはもちろん、商品データだけを更新した場合でも /data/products.js が
    古いキャッシュのまま配信され続けないよう、生成元データもハッシュ対象に含める。"""
    h = hashlib.sha256()
    for sub in ("css", "js"):
        d = ROOT / "assets" / sub
        if not d.exists():
            continue
        for f in sorted(d.glob("*")):
            if f.is_file():
                h.update(f.read_bytes())
    for f in sorted((ROOT / "scripts").glob("data_*.py")):
        h.update(f.read_bytes())
    # 製品SVGは svg_art.py から生成されるため、描画エンジンの変更でも
    # 画像URLの ?v= が変わるようハッシュ対象に含める(旧画像がCDNの
    # immutableキャッシュに残り続ける問題の対策)
    h.update((ROOT / "scripts" / "svg_art.py").read_bytes())
    return h.hexdigest()[:10]


ASSET_V = _asset_version()


def pimg(pid, i=0):
    """製品画像URL(キャッシュバスティング付き)。vercelの/assets/*は
    1年immutableのため、内容が変わったらクエリでURL自体を変える。"""
    return f"/assets/img/products/{pid}-{i}.svg?v={ASSET_V}"


def pimg_front(pid):
    return f"/assets/img/products/{pid}-front.svg?v={ASSET_V}"

PAGES = []  # 検索インデックス + sitemap 用 {url,title,desc,group}


def yen(n):
    return f"¥{n:,}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def num(s):
    m = re.search(r"([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else 0


# ==========================================================================
# チャート(charts.js が data-chart JSON を描画する)
# ==========================================================================

def chart(cfg, cls=""):
    js = json.dumps(cfg, ensure_ascii=False).replace("'", "&#39;")
    return f'<figure class="chart reveal{(" " + cls) if cls else ""}" data-chart=\'{js}\'></figure>'


# ベンチマーク・技術トレンドの単一ソース(架空値)
ANTUTU = {"rai-g1": 158, "rai-g2": 218, "rai-g3": 312, "rai-g4": 385,
          # コラボ専用設計SoC(七耀/残響/夜行/前線。残響=全SUZAKU最高)
          "gensoro-e1": 408, "kyoshin-w1": 418, "yaso-n1": 410, "kikan-f1": 403}   # 万点(旗艦G系)
ANTUTU_E = {"rai-e1": 62, "rai-e2": 85}                                   # 万点(エントリーE系)
TFLOPS_L = {"homura-l1": 0.35, "homura-l2": 0.5}                          # Lite GPU
CLOCK = {"rai-g1": 3.2, "rai-g2": 3.3, "rai-g3": 3.5, "rai-g4": 3.8}    # GHz
NPU_TOPS = {"rai-g1": 20, "rai-g2": 45, "rai-g3": 75, "rai-g4": 120}
TFLOPS = {"homura-x1": 1.0, "homura-x2": 1.6, "homura-x3": 2.3, "homura-x4": 3.4}
MEM_MBPS = {"hayate-m1": 8533, "hayate-m2": 10667}
SSD_MBS = {"shun-s1": 4300, "shun-s2": 5800}
VC_AREA = [("氷刃 V1(2023)", 9000), ("氷刃 V2(2024)", 10200), ("氷刃 V3(2025)", 11000), ("氷刃 V4(2026)", 12800)]
FAN_RPM = [("第1世代(2023)", 18000), ("第2世代(2024-25)", 22000), ("第3世代(2026)", 24000)]
COOL_DELTA = [("氷刃 V1", 9.5), ("氷刃 V2", 12.0), ("氷刃 V3", 14.2), ("氷刃 V4", 16.8)]  # 表面温度低下℃


def product_antutu(p):
    """製品の搭載SoCからAnTuTuスコア(万点)を算出。省電力版(A)は0.74倍。"""
    chip = p.get("chip")
    if not chip:
        return None
    if chip in ANTUTU_E:
        return ANTUTU_E[chip]
    if chip not in ANTUTU:
        return None
    soc = get_spec(p, ["性能"], "SoC")
    base = ANTUTU[chip]
    if re.search(r"RAI-G\dA", soc):
        return round(base * 0.74)
    return base


def product_fps_keep(p):
    """30分後fps維持率(%)。GAME_FPS(FPSタイトル基準)から算出。持続=冷却の実力。
    ゲーミング系ラインのみ対象(省電力版チップの一般/エントリー機は対象外=None)。"""
    if p["line"] not in GAMING_LINES:
        return None
    fps = GAME_FPS.get(p.get("chip"))
    if not fps:
        return None
    avg, sustained = fps[1]  # index1 = NOVA STRIKE(上限解放FPS)を代表値に
    return round(sustained / avg * 100)


def product_touch_ms(p):
    """タッチ応答遅延(ms・推定)。リフレッシュレートから導出(小さいほど良い)。
    「1〜120Hz可変」のような表記は最大値(=最速時)を採用して一意に決める。"""
    s = get_spec(p, ["ディスプレイ"], "リフレッシュレート") or ""
    nums = [int(x) for x in re.findall(r"\d+", s)]
    hz = max(nums) if nums else 60
    return round(1000.0 / hz + 9)


def product_charge50_min(p):
    """0→50%充電の所要時間(分・推定)。容量と有線充電Wから導出(小さいほど良い)。
    0→50%は急速充電が最大電力に近い領域のため、実効効率75%で近似する。"""
    cap = num(get_spec(p, ["バッテリー", "バッテリー・充電"], "バッテリー容量")) \
        or num(get_spec(p, ["バッテリー", "バッテリー・充電"], "容量"))
    watt = num(get_spec(p, ["バッテリー", "バッテリー・充電"], "有線充電"))
    if not cap or not watt:
        return None
    wh_half = cap * 0.5 * 3.85 / 1000.0
    return round(wh_half / (watt * 0.75) * 60)


def product_cost_index(p):
    """コスパ指標: 1万円あたりAnTuTu(万点/万円。大きいほど割安)。現行モデルのみ。"""
    a = product_antutu(p)
    if not a or p["status"] != "current" or not p.get("price"):
        return None
    return round(a / (p["price"] / 10000.0), 1)


_BACK_FX_COLLAB = {"genshin": "元素リング発光", "wuwa": "音叉LED", "nte": "EL発光背面", "endfield": "計器窓・ターミナルHUD"}
_BACK_FX_LINE = {"suzaku": "背面LEDロゴ", "pad": "背面LEDロゴ", "neo": "背面LED", "pad-neo": "背面LED"}


def product_back_fx(p):
    """背面演出(LED・EL・計器窓)。コラボは作品意匠、ゲーミングはLED、その他はなし。"""
    if p.get("collab"):
        return _BACK_FX_COLLAB.get(p["collab"], "コラボ意匠")
    return _BACK_FX_LINE.get(p["line"], "なし")


def product_aod(p):
    """常時表示(AOD)対応。有機EL系パネルは対応、液晶は非対応と判定。"""
    panel = get_spec(p, ["ディスプレイ"], "パネル")
    return "対応" if re.search(r"AMOLED|有機EL|燐光|OLED", panel) else "非対応"


def compare_dash(p):
    """比較ページの実測ダッシュボード行(数値バー付き)。すべて既存単一ソースから導出。
    dir: high=大きいほど良い / low=小さいほど良い。"""
    return [
        {"key": "30分後fps維持率", "v": product_fps_keep(p), "u": "%", "dir": "high"},
        {"key": "タッチ遅延(推定)", "v": product_touch_ms(p), "u": "ms", "dir": "low"},
        {"key": "0→50%充電(推定)", "v": product_charge50_min(p), "u": "分", "dir": "low"},
        {"key": "コスパ(1万円あたり)", "v": product_cost_index(p), "u": "万点", "dir": "high"},
    ]


def radar_values(p):
    """5軸(性能/カメラ/バッテリー/冷却/コスパ)を仕様から算出、0-100。
    コラボ限定モデルは突出軸が機種ごとに異なるため、radar_override を優先する。"""
    if p.get("radar_override"):
        return p["radar_override"]
    perf = round(min(100, (product_antutu(p) or 100) / 385 * 100))
    cam_s = get_spec(p, ["カメラ"], "リアカメラ")
    cam = 95 if "RS-2+" in cam_s else 86 if "RS-2" in cam_s else 72 if "RS-1" in cam_s else 50
    bat = num(get_spec(p, ["バッテリー"], "バッテリー容量"))
    batv = round(min(100, bat / (10500 if p["cat"] == "tablet" else 7600) * 100)) if bat else 40
    cool_s = get_spec(p, ["冷却"], "冷却システム")
    cool = 98 if "V4" in cool_s else 88 if "V3" in cool_s else 76 if "V2" in cool_s else 64 if "V1" in cool_s else 42
    cost = round(max(35, min(100, 100 - (p["price"] - 30000) / 1400)))
    return [perf, cam, batv, cool, cost]


RADAR_AXES = ["性能", "カメラ", "バッテリー", "冷却", "コスパ"]


# ==========================================================================
# 製品ページの追加コンテンツ(同梱物・対応アクセサリ・製品別FAQ)
# ==========================================================================

def box_items(p):
    """同梱物リスト。カテゴリ・ラインごとに現実的な内容を生成。"""
    if p["cat"] == "phone":
        items = ["本体", "USB Type-C to C ケーブル(1m)", "SIMピン", "クイックスタートガイド / 保証のご案内", "SUZAKUステッカー"]
        if p["line"] in ("suzaku", "neo", "collab"):
            watt = num(get_spec(p, ["バッテリー"], "有線充電")) or 65
            items.insert(1, f"雷速チャージャー {watt}W(同梱)")
            items += ["クリアソフトケース", "画面保護フィルム(貼付済み)"]
        return items
    if p["cat"] == "tablet":
        items = ["本体", "USB Type-C to C ケーブル(1.5m)", "クイックスタートガイド / 保証のご案内"]
        if p["line"] in ("pad", "pad-neo"):
            watt = num(get_spec(p, ["バッテリー"], "有線充電")) or 67
            items.insert(1, f"雷速チャージャー {watt}W(同梱)")
        return items
    extra = {
        "hyoran-cooler": ["USB Type-C ケーブル(1.2m)"],
        "grip-pro": ["キャリングポーチ", "USB Type-C ケーブル(0.8m)"],
        "buds": ["充電ケース", "2.4GHz USB-C ドングル", "イヤーピース(XS/S/M/L)"],
        "raisoku-charger": ["120W対応 USB-C ケーブル(1.5m)"],
        "shield-case": ["クリーニングクロス"],
        "dock": ["電源アダプタ(140W)", "HDMI 2.1 ケーブル(1.5m)"],
    }
    return ["本体"] + extra.get(p["id"], []) + ["クイックスタートガイド / 保証のご案内"]


def acc_compat_table(p):
    """スマホ/タブレット向け: 純正アクセサリ対応表。"""
    _collab_phone = {"genshin": ("shichiyo", "七耀"), "wuwa": ("zankyo", "残響"),
                     "nte": ("yako", "夜行"), "endfield": ("zensen", "前線")}

    def compat(acc_id):
        if acc_id == "shield-case":
            return ("対応", "専用設計") if p["id"] == "suzaku-4" else ("非対応", "SUZAKU 4 専用")
        if acc_id.startswith("cs-"):
            pid, name = _collab_phone[acc_id[3:]]
            return ("対応", "専用設計") if p["id"] == pid else ("非対応", f"{name} 専用")
        if acc_id.startswith("bd-"):
            return ("対応", "Bluetooth 5.4 接続")
        if acc_id.startswith("pb-"):
            return ("対応", "マグネット吸着+有線") if p["cat"] == "phone" else ("対応", "有線接続で利用可")
        if acc_id in ("hyoran-cooler", "grip-pro"):
            return ("対応", "幅67〜82mm") if p["cat"] == "phone" else ("非対応", "スマートフォン専用")
        if acc_id == "dock":
            wl = "ワイヤレス充電も利用可" if p["id"] in ("suzaku-4",) else "有線接続で利用可"
            return ("対応", wl)
        return ("対応", "全機種対応")

    rows = ""
    for a in ACCESSORIES:
        if a["status"] != "current":
            continue
        ok, note = compat(a["id"])
        mark = ('<strong style="color:var(--accent)">対応</strong>' if ok == "対応"
                else '<span class="t-faint">—</span>')
        rows += (f'<tr><td><a href="{product_url(a)}" style="color:var(--accent);font-weight:700">{esc(a["name"])}</a></td>'
                 f'<td>{yen(a["price"])}</td><td>{mark}</td><td class="t-soft">{esc(note)}</td></tr>')
    return f"""
<div class="scroll-x reveal"><table class="spec-table quick-table">
  <thead><tr><th scope="col">アクセサリ</th><th scope="col">価格(税込)</th><th scope="col">{esc(p['name'])}</th><th scope="col">備考</th></tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""


LINE_FAQ = {
    "biz": [
        ("個人でも購入できますか?",
         "KANAME B1 は法人運用(MDM管理・キッティング・保守契約)を前提に設計された法人専用モデルで、個人向けの単体販売は行っていません。導入は<a href='/business/store/'>法人向けストア</a>のお見積り・ご相談から、<a href='/business/contact/'>法人窓口</a>経由のご契約が対象です。"),
        ("カメラレス仕様は後からカメラを追加できますか?",
         "できません。カメラレス仕様はソフトウェアでの無効化ではなく、カメラモジュールを物理的に搭載しない構成です。撮影禁止区域の持ち込み審査でも、背面のSECURE刻印と型番で判別できます。"),
        ("MDMは何に対応していますか?",
         "主要なMDM(EMM)サービスのゼロタッチ登録に対応します。端末IDの事前登録により、開梱後の初回起動で自動的にポリシーが適用されます。詳細な対応一覧は法人窓口へお問い合わせください。"),
        ("保守はどのような内容ですか?",
         "法人契約でセキュリティ更新5年+引取交換保守を提供します。故障時は代替機を先出しし、業務停止時間を最小化します。"),
    ],
    "suzaku": [
        ("ファンの音はゲーム中どのくらい聞こえますか?",
         "自動モードでは28〜38dB(ささやき声〜静かな図書館程度)で制御されます。動画視聴などの低負荷時はファンは停止します。「陣」から手動で4段階+停止を選択できます。"),
        ("冷却用の通気口があっても防水は大丈夫ですか?",
         "IP54(防塵・防滴)に対応しています。エアダクトを迷路状に設計し、雨滴や手汗が内部へ到達しない構造です。ただし水没には対応しないため、入浴・水泳でのご使用はお避けください。"),
        ("発熱で性能が落ちる「サーマルスロットリング」は起きませんか?",
         "60分の高負荷連続プレイを想定した当社試験では、フレームレート低下5%未満を維持しています。氷刃ベイパーチャンバー・旋風ファン・液焔の多層冷却と、神楽サーマルの予測制御によるものです。"),
    ],
    "neo": [
        ("フラッグシップとの違いは何ですか?",
         "SoC・冷却は前年フラッグシップと同一で、ディスプレイのピーク輝度・カメラ構成・充電速度などを合理化しています。ゲーム性能そのものは前年旗艦とほぼ同等です。<a href='/products/compare/'>比較ツール</a>で並べてご確認ください。"),
        ("ショルダートリガーは搭載されていますか?",
         "はい。Neoシリーズ全機種に静電容量式ショルダートリガーを搭載しています。「陣」のエアトリガー設定から感度・割当を調整できます。"),
        ("何年使えますか?",
         "OSアップデート2世代+セキュリティ更新4年を保証しています。バッテリーは充電上限設定・バイパス充電で劣化を抑えられます。"),
    ],
    "tsubame": [
        ("ゲーミングスマホのような派手なデザインではありませんか?",
         "はい。TSUBAMEは日本の伝統色とマット仕上げの落ち着いたデザインです。SUZAKU OSも「ピュアモード」が初期設定で、ゲーム機能は必要な時だけ呼び出せます。"),
        ("カメラの画質はフラッグシップと同じですか?",
         "TSUBAME 3はフラッグシップと同じ「天眼 RS-2+」センサーを搭載しています。望遠レンズの有無などの構成差はありますが、広角カメラの画質は同水準です。"),
        ("おサイフケータイ・防水は使えますか?",
         "FeliCa(おサイフケータイ)とIP68防塵防水に対応しています。日常利用の安心を最優先した設計です。"),
    ],
    "lite": [
        ("価格が安い理由は何ですか?",
         "エントリー専用に新設計した自社SoC「雷 RAI-E」シリーズの採用、液晶ディスプレイの選択、パッケージの簡素化によるものです。FeliCa・防水・セキュリティ更新など「毎日の安心」に関わる部分は削っていません。<a href='/tech/cpu/rai-e2/'>RAI-E2の技術詳細</a>もご覧ください。"),
        ("ゲームはどの程度動きますか?",
         "人気タイトルの標準〜中設定で快適に動作します。高フレームレート・最高画質でのプレイをご希望の場合はNeoシリーズをご検討ください。"),
        ("初めてのスマホでも使えますか?",
         "かんたんホーム、文字サイズの一括拡大、迷惑電話ブロックなど、初めての方向けの機能を標準搭載しています。"),
    ],
    "acc": [
        ("他社製スマートフォンでも使えますか?",
         "Bluetooth・USB-C等の標準規格に準拠しているため、多くの他社製端末でも基本機能はご利用いただけます。ただし「陣」との連携機能(自動起動・プロファイル同期など)はSUZAKU端末専用です。"),
        ("保証期間はどのくらいですか?",
         "ご購入日から1年間のメーカー保証が付属します。詳細は<a href='/support/warranty/'>保証について</a>をご覧ください。"),
        ("本体と同時購入するメリットはありますか?",
         "税込5,000円以上で送料無料になるほか、ストアのカートで本体とまとめて一度に受け取れます。"),
    ],
}
LINE_FAQ["pad"] = LINE_FAQ["suzaku"]
LINE_FAQ["pad-neo"] = LINE_FAQ["neo"]
LINE_FAQ["t-pad"] = LINE_FAQ["tsubame"]
LINE_FAQ["t-pad-lite"] = LINE_FAQ["lite"]
LINE_FAQ["collab"] = [
    ("コラボモデルは数量限定・期間限定ですか?",
     "はい。各コラボレーションモデルは数量限定生産・期間限定販売です。特設ページに残りの販売枠と受付終了までのカウントダウンを表示しています。上限に達した場合は期間内でも販売を終了します。"),
    ("性能は通常モデルと違いますか?",
     "コラボモデルは既存機の色替えではなく、筐体・ディスプレイ・カメラ・電池からSoC(元素炉/共振/夜想/基幹)まで作品ごとにゼロから共同設計したオリジナル端末です。性能の性格も機種ごとに異なります(例: 残響はAnTuTu 418万点でSUZAKU史上最速、前線は30分後fps維持率99%)。詳細は各特設ページをご覧ください。"),
    ("同梱のゲーム内アイテムコードは実際に使えますか?",
     "本サイトは架空のデモです。コラボレーション企画・同梱コードはデモ表記であり、実在の商品・提携・引き換えを示すものではありません。"),
] + LINE_FAQ["suzaku"]

GAMING_LINES = {"suzaku", "neo", "pad", "pad-neo", "collab"}
LIFE_LINES = {"tsubame", "lite", "t-pad", "t-pad-lite"}

# チップ世代別 タイトル実測fps: (平均fps, 30分後fps) ×4ジャンル(架空タイトル)
GAME_TITLES = [
    ("幻晶のエルド", "オープンワールドRPG", "最高画質 / 60fps上限"),
    ("NOVA STRIKE", "FPSシューター", "最高画質 / 上限解放"),
    ("頂上決戦アリーナ", "MOBA", "最高画質 / 上限解放"),
    ("雷鳴レーシング8", "レーシング", "最高画質 / 上限解放"),
]
GAME_FPS = {
    "rai-g1": [(55, 48), (88, 79), (118, 112), (86, 77)],
    "rai-g2": [(59, 55), (116, 108), (142, 137), (108, 101)],
    "rai-g3": [(60, 59), (143, 138), (164, 160), (132, 127)],
    "rai-g4": [(60, 60), (172, 170), (175, 175), (158, 155)],
    "gensoro-e1": [(60, 60), (143, 142), (144, 144), (140, 138)],
    "kyoshin-w1": [(60, 60), (185, 184), (185, 185), (168, 166)],
    "yaso-n1": [(60, 60), (164, 162), (165, 165), (152, 150)],
    "kikan-f1": [(60, 60), (144, 143), (144, 144), (142, 141)],
}


def game_fps_section(p):
    """ゲーミング系ライン専用: タイトル別実測パフォーマンス表。"""
    fps = GAME_FPS.get(p["chip"])
    if not fps:
        return ""
    rows = ""
    for (title, genre, setting), (avg, sustained) in zip(GAME_TITLES, fps):
        keep = round(sustained / avg * 100)
        rows += (f'<tr><th scope="row">{title}<br><small class="t-faint">{genre}</small></th>'
                 f'<td>{setting}</td><td><strong>{avg}fps</strong></td>'
                 f'<td>{sustained}fps <small class="t-faint">(維持率{keep}%)</small></td></tr>')
    return f"""
<section class="section--sm" id="game-ready">
  <div class="container">
    <div class="section-head"><p class="eyebrow">GAME READY</p><h2 class="t-h2">タイトル別 実測パフォーマンス</h2>
    <p class="t-soft t-small">室温25℃・輝度50%・Wi-Fi接続の当社試験値(タイトルは検証用の架空タイトル)。「30分後」は連続プレイでの持続性能 — 冷却の実力はここに出ます。</p></div>
    <div class="scroll-x reveal"><table class="spec-table quick-table">
      <thead><tr><th scope="col">タイトル</th><th scope="col">画質設定</th><th scope="col">平均fps</th><th scope="col">30分後fps</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
    <p class="t-micro t-faint" style="margin-top:14px">ゲーム側からの性能制御は<a href="/developers/docs/performance-api/" style="color:var(--accent);text-decoration:underline">Performance API</a>で開発者に開放しています。</p>
  </div>
</section>"""


def battery_life_section(p):
    """スタンダード/エントリー系ライン専用: 電池持ちと充電の目安表。"""
    bat = num(get_spec(p, ["バッテリー"], "バッテリー容量"))
    watt = num(get_spec(p, ["バッテリー"], "有線充電"))
    if not bat:
        return ""
    tablet = p["cat"] == "tablet"
    video = round(bat / (640 if tablet else 195))
    browse = round(video * 0.7)
    call = round(video * 0.35)
    recover = min(85, round((watt or 18) * 0.7))
    rows = (
        f'<tr><th scope="row">動画の連続再生</th><td><strong>約{video}時間</strong></td><td>フル充電から・機内モード</td></tr>'
        f'<tr><th scope="row">SNS・ブラウジング</th><td><strong>約{browse}時間</strong></td><td>5G接続・画面点灯連続</td></tr>'
        f'<tr><th scope="row">ビデオ通話</th><td><strong>約{call}時間</strong></td><td>Wi-Fi接続・インカメラ使用</td></tr>'
        f'<tr><th scope="row">30分の充電で</th><td><strong>約{recover}%まで回復</strong></td><td>{watt}W急速充電・電源オフ時</td></tr>')
    return f"""
<section class="section--sm" id="battery-life">
  <div class="container">
    <div class="section-head"><p class="eyebrow">BATTERY LIFE</p><h2 class="t-h2">電池持ちと充電の目安</h2>
    <p class="t-soft t-small">輝度50%・当社試験条件での参考値です。使用状況により変動します。</p></div>
    <div class="scroll-x reveal"><table class="spec-table quick-table">
      <thead><tr><th scope="col">使い方</th><th scope="col">{esc(p['name'])}</th><th scope="col">条件</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
    <p class="t-micro t-faint" style="margin-top:14px">いたわり充電(充電上限80%設定)を使うと、2年後の電池劣化を大幅に抑えられます。</p>
  </div>
</section>"""


# アクセサリ製品別の比較チャート(製品の性格をデータで示す)
ACC_CHARTS = {
    "hyoran-cooler": {"type": "bar", "title": "背面温度の低下量(SUZAKU 4・30分高負荷時)", "unit": "℃",
                      "labels": ["冷却なし", "初代 氷嵐クーラー", "氷嵐クーラー 2"], "values": [0, 19, 28], "highlight": 2},
    "grip-pro": {"type": "bar", "title": "入力遅延の比較(ボタン押下→画面反映)", "unit": "ms",
                 "labels": ["一般的なBluetoothパッド", "Grip Pro(Bluetooth)", "Grip Pro(USB-C直結)"], "values": [45, 12, 0.8], "highlight": 2},
    "buds": {"type": "bar", "title": "音声遅延の比較", "unit": "ms",
             "labels": ["一般的なTWS(AAC)", "低遅延モード搭載TWS", "SUZAKU Buds(2.4GHzドングル)"], "values": [180, 80, 38], "highlight": 2},
    "raisoku-charger": {"type": "bar", "title": "SUZAKU 4 のフル充電時間比較", "unit": "分",
                        "labels": ["一般的な30W充電器", "65W級充電器", "雷速チャージャー 120W"], "values": [78, 52, 34], "highlight": 2},
    "shield-case": {"type": "bar", "title": "ケース装着による背面温度上昇(30分高負荷)", "unit": "℃",
                    "labels": ["手帳型ケース", "一般的なTPUケース", "SUZAKU Shield"], "values": [9.2, 6.8, 1.9], "highlight": 2},
    "dock": {"type": "bar", "title": "ワイヤレス給電出力の比較", "unit": "W",
             "labels": ["Qi(EPP)", "Qi2", "SUZAKU Dock(対応機種)"], "values": [15, 25, 80], "highlight": 2},
}


# ==========================================================================
# 共通レイアウト
# ==========================================================================

def mega_products():
    def li(url, label, small=None, strong=False):
        lbl = f"<strong>{label}</strong>" if strong else label
        sm = f"<small>{small}</small>" if small else ""
        return f'<li><a href="{url}">{lbl}{sm}</a></li>'

    return f"""
<div class="mega" style="--mega-cols:4">
  <div class="mega__inner">
    <div>
      <p class="mega__group-title">スマートフォン</p>
      <ul class="mega__list">
        {li('/products/phone/suzaku-4/', 'SUZAKU 4', 'ゲーミングフラッグシップ', True)}
        {li('/products/phone/suzaku-3/', 'SUZAKU 3', 'ゲーミングフラッグシップ')}
        {li('/products/phone/neo-3/', 'SUZAKU Neo 3', 'ゲーミングスタンダード')}
        {li('/products/phone/tsubame-3/', 'TSUBAME 3', 'スタンダード')}
        {li('/products/phone/tsubame-lite-2/', 'TSUBAME Lite 2', 'エントリー')}
        {li('/products/phone/', 'すべてのスマートフォン')}
        {li('/products/finder/', '製品セレクター', '3問であなたの一台')}
      </ul>
    </div>
    <div>
      <p class="mega__group-title">タブレット</p>
      <ul class="mega__list">
        {li('/products/tablet/pad-2/', 'SUZAKU Pad 2', 'ゲーミング', True)}
        {li('/products/tablet/pad-neo/', 'SUZAKU Pad Neo', 'ゲーミング')}
        {li('/products/tablet/t-pad-2/', 'TSUBAME Pad 2', 'スタンダード')}
        {li('/products/tablet/t-pad-lite/', 'TSUBAME Pad Lite', 'エントリー')}
        {li('/products/tablet/', 'すべてのタブレット')}
      </ul>
    </div>
    <div>
      <p class="mega__group-title">アクセサリ</p>
      <ul class="mega__list">
        {li('/products/accessories/hyoran-cooler/', '氷嵐クーラー 2')}
        {li('/products/accessories/grip-pro/', 'SUZAKU Grip Pro')}
        {li('/products/accessories/buds/', 'SUZAKU Buds')}
        {li('/products/accessories/raisoku-charger/', '雷速チャージャー 120W')}
        {li('/products/accessories/', 'すべてのアクセサリ')}
      </ul>
    </div>
    <div>
      <p class="mega__group-title">ショッピング</p>
      <ul class="mega__list">
        {li('/collab/', 'コラボレーション', '数量限定・期間限定', True)}
        {li('/store/', 'SUZAKU ストア')}
        {li('/store/deals/', '特集・キャンペーン')}
        {li('/store/trade-in/', '下取りプログラム')}
        {li('/store/gift/', 'ギフトガイド')}
        {li('/store/guide/', '購入ガイド')}
      </ul>
    </div>
  </div>
</div>"""


def mega_tech():
    def li(url, label, small=None):
        sm = f"<small>{small}</small>" if small else ""
        return f'<li><a href="{url}">{label}{sm}</a></li>'

    return f"""
<div class="mega" style="--mega-cols:4">
  <div class="mega__inner">
    <div>
      <p class="mega__group-title">自社シリコン</p>
      <ul class="mega__list">
        {li('/tech/cpu/', '雷 RAI', 'CPU / SoC')}
        {li('/tech/gpu/', '焔 HOMURA', 'GPU')}
        {li('/tech/memory/', '疾風 HAYATE', 'メモリ')}
        {li('/tech/storage/', '瞬 SHUN', 'ストレージ')}
      </ul>
    </div>
    <div>
      <p class="mega__group-title">冷却技術</p>
      <ul class="mega__list">
        {li('/tech/cooling/hyojin/', '氷刃', 'ベイパーチャンバー')}
        {li('/tech/cooling/senpu/', '旋風', '内蔵アクティブファン')}
        {li('/tech/cooling/ekien/', '液焔', 'リキッドメタル')}
        {li('/tech/cooling/suiryu/', '水龍', '能動液冷(次世代)')}
        {li('/tech/cooling/', '冷却技術のすべて')}
      </ul>
    </div>
    <div>
      <p class="mega__group-title">イメージング & AI</p>
      <ul class="mega__list">
        {li('/tech/camera/', '天眼 TENGAN', 'カメラシステム')}
        {li('/tech/ai/', '神楽 KAGURA', 'AIエンジン')}
        {li('/tech/display/', '燐光 RINKO', 'ディスプレイ')}
      </ul>
    </div>
    <div>
      <p class="mega__group-title">ソフトウェア</p>
      <ul class="mega__list">
        {li('/os/v4/', 'SUZAKU OS 4.0', '最新バージョン「不知火」')}
        {li('/os/game-space/', 'ゲームスペース「陣」')}
        {li('/os/', 'SUZAKU OS トップ')}
        {li('/tech/', 'テクノロジー トップ')}
      </ul>
    </div>
  </div>
</div>"""


def mega_company():
    return """
<div class="mega" style="--mega-cols:3">
  <div class="mega__inner">
    <div>
      <p class="mega__group-title">企業情報</p>
      <ul class="mega__list">
        <li><a href="/company/">会社概要</a></li>
        <li><a href="/company/history/">沿革 — SUZAKUの歴史</a></li>
        <li><a href="/company/ignite/">IGNITE 発表会</a></li>
        <li><a href="/company/leadership/">経営陣</a></li>
        <li><a href="/company/ir/">投資家情報</a></li>
        <li><a href="/news/">ニュースルーム</a></li>
        <li><a href="/company/careers/">採用情報</a></li>
      </ul>
    </div>
    <div>
      <p class="mega__group-title">取り組み</p>
      <ul class="mega__list">
        <li><a href="/sustainability/">環境への取り組み</a></li>
        <li><a href="/sustainability/recycle/">回収・リサイクル</a></li>
        <li><a href="/legal/accessibility/">アクセシビリティ</a></li>
        <li><a href="/legal/">法的情報</a></li>
      </ul>
    </div>
    <div>
      <p class="mega__group-title">パートナー・コミュニティ</p>
      <ul class="mega__list">
        <li><a href="/community/">コミュニティ</a></li>
        <li><a href="/community/esports/">eスポーツ・大会</a></li>
        <li><a href="/business/">法人のお客様</a></li>
        <li><a href="/developers/">開発者向け</a></li>
      </ul>
    </div>
  </div>
</div>"""


# カラーテーマの選択肢(単一ソース)。テーマを追加・変更する場合はここだけを編集すれば、
# ヘッダーのドロップダウンとドロワーのセグメント切替の両方に反映される。
# 各要素: (value, スウォッチのCSS, 正式名称(aria/トースト), 短縮名(ドロワー用))
THEME_OPTS = [
    ("auto", "linear-gradient(90deg,#fafafc 50%,#0b0b10 50%)", "ページ既定", "既定"),
    ("light", "#fafafc", "ライト", "ライト"),
    ("dark", "#0b0b10", "ダーク", "ダーク"),
    ("g", "linear-gradient(135deg,#00e68a,#00c2ff)", "Gモード", "G"),
    ("suzaku", "linear-gradient(135deg,#e8442e,#d9a441)", "朱雀モード", "朱雀"),
]


def theme_menu_buttons():
    """ヘッダーのテーマドロップダウン用ボタン列。"""
    return "".join(
        f'<button type="button" data-theme-opt="{v}" role="menuitemradio"><i style="background:{sw}"></i>{full}</button>'
        for v, sw, full, short in THEME_OPTS
    )


def theme_seg_buttons():
    """ドロワー(モバイル)のテーマセグメント用ボタン列。"""
    return "".join(
        f'<button type="button" data-theme-opt="{v}" data-theme-label="{full}"><i style="background:{sw}"></i>{short}</button>'
        for v, sw, full, short in THEME_OPTS
    )


def header_html():
    return f"""
<a class="skip-link" href="#main">本文へスキップ</a>
<header class="site-header" id="siteHeader">
  <div class="site-header__inner">
    <a class="brand" href="/" aria-label="SUZAKU ホーム">{svg_art.BRAND_MARK}<span>SUZAKU</span></a>
    <nav class="gnav" aria-label="グローバルナビゲーション">
      <div class="gnav__item"><a class="gnav__link" href="/products/">製品</a>{mega_products()}</div>
      <div class="gnav__item"><a class="gnav__link" href="/tech/">テクノロジー</a>{mega_tech()}</div>
      <div class="gnav__item"><a class="gnav__link" href="/os/">OS</a></div>
      <div class="gnav__item"><a class="gnav__link" href="/store/">ストア</a></div>
      <div class="gnav__item"><a class="gnav__link" href="/support/">サポート</a></div>
      <div class="gnav__item"><a class="gnav__link" href="/community/">コミュニティ</a></div>
      <div class="gnav__item"><a class="gnav__link" href="/company/">企業情報</a>{mega_company()}</div>
    </nav>
    <div class="header-actions">
      <div class="theme-menu" id="themeMenu">
        <button class="icon-btn" id="themeBtn" aria-label="カラーテーマを変更" aria-expanded="false" aria-haspopup="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" stroke="none"/></svg>
        </button>
        <div class="theme-menu__panel" role="menu" aria-label="カラーテーマ">
          <p class="theme-menu__title">カラーテーマ</p>
          {theme_menu_buttons()}
        </div>
      </div>
      <a class="icon-btn" href="/search/" aria-label="検索">{svg_art.ICONS['search']}</a>
      <a class="icon-btn" href="/account/login/" id="accountLink" aria-label="アカウント">{svg_art.ICONS['user']}</a>
      <a class="icon-btn" href="/store/cart/" aria-label="カート">{svg_art.ICONS['cart']}<span class="cart-badge" id="cartBadge"></span></a>
      <button class="icon-btn nav-toggle" id="navToggle" aria-label="メニュー" aria-expanded="false"><span></span></button>
    </div>
  </div>
</header>
<nav class="drawer" id="drawer" aria-label="モバイルナビゲーション">
  <div class="drawer__group">
    <button class="drawer__summary" type="button" aria-expanded="false" aria-controls="drawer-products">製品</button>
    <div class="drawer__panel" id="drawer-products"><div class="drawer__panel-inner">
      <p class="drawer__sub">スマートフォン</p>
      <a href="/products/phone/suzaku-4/">SUZAKU 4</a>
      <a href="/products/phone/neo-3/">SUZAKU Neo 3</a>
      <a href="/products/phone/tsubame-3/">TSUBAME 3</a>
      <a href="/products/phone/tsubame-lite-2/">TSUBAME Lite 2</a>
      <a href="/products/phone/">すべてのスマートフォン</a>
      <p class="drawer__sub">タブレット</p>
      <a href="/products/tablet/pad-2/">SUZAKU Pad 2</a>
      <a href="/products/tablet/">すべてのタブレット</a>
      <p class="drawer__sub">アクセサリ・ツール</p>
      <a href="/products/accessories/">すべてのアクセサリ</a>
      <a href="/products/compare/">製品を比較する</a>
      <a href="/products/finder/">製品セレクター</a>
      <a href="/collab/">コラボレーション</a>
    </div></div>
  </div>
  <div class="drawer__group">
    <button class="drawer__summary" type="button" aria-expanded="false" aria-controls="drawer-tech">テクノロジー</button>
    <div class="drawer__panel" id="drawer-tech"><div class="drawer__panel-inner">
      <a href="/tech/">テクノロジー トップ</a>
      <a href="/tech/cpu/">雷 RAI(CPU)</a>
      <a href="/tech/gpu/">焔 HOMURA(GPU)</a>
      <a href="/tech/memory/">疾風 HAYATE(メモリ)</a>
      <a href="/tech/storage/">瞬 SHUN(ストレージ)</a>
      <a href="/tech/cooling/">冷却技術</a>
      <a href="/tech/camera/">天眼 カメラ</a>
      <a href="/tech/ai/">神楽 AIエンジン</a>
      <a href="/tech/display/">燐光 ディスプレイ</a>
    </div></div>
  </div>
  <div class="drawer__group">
    <button class="drawer__summary" type="button" aria-expanded="false" aria-controls="drawer-os">SUZAKU OS</button>
    <div class="drawer__panel" id="drawer-os"><div class="drawer__panel-inner">
      <a href="/os/">SUZAKU OS トップ</a>
      <a href="/os/v4/">SUZAKU OS 4.0「不知火」</a>
      <a href="/os/game-space/">ゲームスペース「陣」</a>
    </div></div>
  </div>
  <a class="drawer__direct" href="/store/">ストア</a>
  <a class="drawer__direct" href="/support/">サポート</a>
  <div class="drawer__group">
    <button class="drawer__summary" type="button" aria-expanded="false" aria-controls="drawer-community">コミュニティ</button>
    <div class="drawer__panel" id="drawer-community"><div class="drawer__panel-inner">
      <a href="/community/">コミュニティ トップ</a>
      <a href="/community/esports/">eスポーツ・大会</a>
      <a href="/community/ambassador/">アンバサダープログラム</a>
    </div></div>
  </div>
  <div class="drawer__group">
    <button class="drawer__summary" type="button" aria-expanded="false" aria-controls="drawer-company">企業情報</button>
    <div class="drawer__panel" id="drawer-company"><div class="drawer__panel-inner">
      <a href="/company/">会社概要</a>
      <a href="/company/history/">沿革</a>
      <a href="/news/">ニュースルーム</a>
      <a href="/company/careers/">採用情報</a>
      <a href="/sustainability/">環境への取り組み</a>
      <a href="/business/">法人のお客様</a>
      <a href="/developers/">開発者向け</a>
    </div></div>
  </div>
  <a class="drawer__direct" href="/search/">検索</a>
  <a class="drawer__direct" href="/account/login/">ログイン / マイページ</a>
  <a class="drawer__direct" href="/settings/">設定</a>
  <div class="drawer__theme">
    <p class="drawer__sub">カラーテーマ</p>
    <div class="theme-seg" role="group" aria-label="カラーテーマ">
      {theme_seg_buttons()}
    </div>
  </div>
</nav>"""


def footer_html():
    col = lambda title, items: (
        f'<div><p class="footer-map__title">{title}</p><ul>'
        + "".join(f'<li><a href="{u}">{t}</a></li>' for t, u in items)
        + "</ul></div>"
    )
    cols = [
        col("製品とストア", [
            ("SUZAKU 4", "/products/phone/suzaku-4/"),
            ("SUZAKU Neo 3", "/products/phone/neo-3/"),
            ("TSUBAME 3", "/products/phone/tsubame-3/"),
            ("SUZAKU Pad 2", "/products/tablet/pad-2/"),
            ("アクセサリ", "/products/accessories/"),
            ("コラボレーション", "/collab/"),
            ("コラボ限定シリコン", "/collab/silicon/"),
            ("SUZAKU ストア", "/store/"),
            ("特集・キャンペーン", "/store/deals/"),
            ("下取りプログラム", "/store/trade-in/"),
            ("SUZAKU Care(延長保証)", "/store/care/"),
            ("ギフトガイド", "/store/gift/"),
            ("製品を比較する", "/products/compare/"),
            ("購入ガイド", "/store/guide/"),
        ]),
        col("テクノロジー", [
            ("雷 RAI(CPU)", "/tech/cpu/"),
            ("焔 HOMURA(GPU)", "/tech/gpu/"),
            ("疾風 HAYATE(メモリ)", "/tech/memory/"),
            ("瞬 SHUN(ストレージ)", "/tech/storage/"),
            ("冷却技術", "/tech/cooling/"),
            ("天眼 カメラ", "/tech/camera/"),
            ("SUZAKU OS", "/os/"),
        ]),
        col("サポート", [
            ("サポートトップ", "/support/"),
            ("よくあるご質問", "/support/faq/"),
            ("用語集", "/support/glossary/"),
            ("トラブルシューティング", "/support/troubleshooting/"),
            ("修理のお申し込み", "/support/repair/"),
            ("修理状況の確認", "/support/status/"),
            ("保証について", "/support/warranty/"),
            ("ダウンロード", "/support/downloads/"),
            ("お問い合わせ", "/support/contact/"),
            ("注文状況の確認", "/store/order-status/"),
            ("マイページ / ログイン", "/account/login/"),
            ("メンテナンス情報", "/maintenance/"),
            ("表示設定", "/settings/"),
        ]),
        col("SUZAKUについて", [
            ("会社概要", "/company/"),
            ("沿革", "/company/history/"),
            ("IGNITE 発表会", "/company/ignite/"),
            ("経営陣", "/company/leadership/"),
            ("投資家情報", "/company/ir/"),
            ("拠点・アクセス", "/company/locations/"),
            ("ニュースルーム", "/news/"),
            ("プレスキット", "/news/press-kit/"),
            ("採用情報", "/company/careers/"),
            ("コミュニティ", "/community/"),
            ("eスポーツ・大会", "/community/esports/"),
            ("アンバサダー", "/community/ambassador/"),
            ("環境への取り組み", "/sustainability/"),
            ("回収・リサイクル", "/sustainability/recycle/"),
        ]),
        col("法人・開発者", [
            ("法人のお客様", "/business/"),
            ("法人向けソリューション", "/business/solutions/"),
            ("導入事例", "/business/cases/"),
            ("法人お問い合わせ", "/business/contact/"),
            ("開発者向け", "/developers/"),
            ("ドキュメント", "/developers/docs/"),
            ("最適化ガイドライン", "/developers/guidelines/"),
            ("対応タイトル", "/developers/showcase/"),
            ("SDKダウンロード", "/developers/sdk/"),
        ]),
    ]
    legal_links = [
        ("プライバシーポリシー", "/legal/privacy/"),
        ("Cookieポリシー", "/legal/cookie/"),
        ("外部送信ポリシー", "/legal/external-transmission/"),
        ("利用規約", "/legal/terms/"),
        ("販売条件", "/legal/sales/"),
        ("特定商取引法に基づく表記", "/legal/tokushoho/"),
        ("保証規定", "/legal/warranty-policy/"),
        ("情報セキュリティ基本方針", "/legal/security/"),
        ("脆弱性開示ポリシー", "/legal/vulnerability-disclosure/"),
        ("AI利用方針", "/legal/ai/"),
        ("コンプライアンス", "/legal/compliance/"),
        ("反社会的勢力への対応", "/legal/anti-social/"),
        ("アクセシビリティ", "/legal/accessibility/"),
        ("知的財産", "/legal/ip/"),
        ("法的情報", "/legal/"),
    ]
    legal = "".join(f'<a href="{u}">{t}</a>' for t, u in legal_links)
    return f"""
<footer class="site-footer">
  <div class="container">
    <div class="footer-map">{''.join(cols)}</div>
    <div class="site-footer__legal">
      <p>本サイトは、架空の企業「株式会社朱雀(SUZAKU Inc.)」のデモンストレーションサイトです。掲載されている製品・価格・技術・サービスはすべてフィクションであり、実在の商品・役務の販売を行うものではありません。</p>
      <div class="site-footer__legal-links">{legal}<button type="button" class="cookie-settings-link" id="cookieSettingsBtn">Cookie設定</button></div>
      <div class="spread">
        <p>Copyright © 2022-2026 SUZAKU Inc. All rights reserved.</p>
        <p>日本 — 東京都千代田区外神田(秋葉原)</p>
      </div>
    </div>
  </div>
</footer>
<div class="cookie-banner" id="cookieBanner" role="dialog" aria-label="Cookieの利用について">
  <p class="cookie-banner__title"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><circle cx="9" cy="10" r="0.5"/><circle cx="14.5" cy="14" r="0.5"/><circle cx="13" cy="8.5" r="0.5"/><circle cx="9.5" cy="15" r="0.5"/><circle cx="15" cy="10.5" r="0.5"/></svg> Cookieの利用について</p>
  <p>当サイトは、サイトの基本機能に必要なCookie等に加え、利便性向上・利用状況分析のためにCookieおよび類似技術を使用します。詳細は<a href="/legal/cookie/">Cookieポリシー</a>および<a href="/legal/external-transmission/">外部送信ポリシー</a>をご覧ください。「設定」からカテゴリごとに選択できます。</p>
  <div class="cluster">
    <button class="btn btn--primary btn--sm" id="consentAcceptAll">すべて同意する</button>
    <button class="btn btn--ghost btn--sm" id="consentRejectAll">必須のみ許可</button>
    <button class="btn btn--soft btn--sm" id="consentOpenSettings">設定</button>
  </div>
</div>
<div class="modal-backdrop" id="consentModal" aria-hidden="true">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="consentModalTitle">
    <div class="stack">
      <h2 class="t-h3" id="consentModalTitle">Cookie設定</h2>
      <p class="t-small t-soft">カテゴリごとにCookie等の利用可否を選択できます。選択内容はこの端末に保存され、<a href="/legal/cookie/" style="color:var(--accent);text-decoration:underline">Cookieポリシー</a>のページからいつでも変更できます。</p>
    </div>
    <div>
      <div class="consent-row">
        <div><p class="consent-row__title">必須Cookie</p><p>カート、ログイン状態、Cookie同意の記録など、サイトの動作に不可欠なもの。無効にできません。</p></div>
        <label class="switch"><input type="checkbox" checked disabled><span class="switch__track"></span></label>
      </div>
      <div class="consent-row">
        <div><p class="consent-row__title">分析Cookie</p><p>ページの利用状況を統計的に把握し、サイト改善に役立てます(アクセス解析)。</p></div>
        <label class="switch"><input type="checkbox" id="consentAnalytics"><span class="switch__track"></span></label>
      </div>
      <div class="consent-row">
        <div><p class="consent-row__title">マーケティングCookie</p><p>興味・関心に基づく情報提供や、広告効果の測定に使用します。</p></div>
        <label class="switch"><input type="checkbox" id="consentMarketing"><span class="switch__track"></span></label>
      </div>
    </div>
    <div class="cluster">
      <button class="btn btn--primary" id="consentSave">選択を保存</button>
      <button class="btn btn--ghost" id="consentModalClose">閉じる</button>
    </div>
    <p class="t-micro t-faint">表示が崩れる、更新した内容が反映されない場合は<button type="button" class="cookie-settings-link clear-cache-trigger">キャッシュを削除</button>できます。</p>
  </div>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>"""


# フォントは非ブロッキング読み込み(media=print→onloadでall)。
# 取得がスタールしてもレンダリング・スクリプト実行を阻害しない。
HEAD_FONTS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" media="print" onload="this.media='all'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap"></noscript>"""


def render_page(url, title, desc, body, theme="dark", crumbs=None, group="その他", noindex=False,
                layout=None, collab=None, collab_lp=True):
    """共通レイアウトでページを組み立ててディスクに書き出す。

    layout=="collab" のとき、コラボ特設専用のスタイル(collab.css)・スクリプト(collab.js)を
    そのページだけ注入し、collab(=data_collab.py の設定dict)の tokens を CSS変数として
    <body> にインライン注入する。色替えは tokens の1行編集で確実に効く。通常ページには一切影響しない。"""
    full_title = f"{title} | {SITE_NAME}" if url != "/" else f"{SITE_NAME} 公式サイト | {title}"
    collab_head = collab_body_class = collab_body_attr = collab_script = ""
    if layout == "collab" and collab:
        tok = collab["tokens"]
        slug = collab["slug"]
        # 第2弾ティザーは複数スラッグ(next-2/3/4)が collab-next の CSS/JS と .collab--next を
        # 共有する。assets_slug 未指定の既存コラボは従来どおり slug をそのまま使う。
        aslug = collab.get("assets_slug", slug)
        collab_head = (f'<link rel="stylesheet" href="/assets/css/collab-core.css?v={ASSET_V}">'
                       f'<link rel="stylesheet" href="/assets/css/collab-{aslug}.css?v={ASSET_V}">'
                       + COLLAB_FONTS.get(aslug, ""))
        # cl-lp はLP/シリコン等の「専用レイアウトページ」のみ。コラボ製品ページは
        # 通常レイアウトのままフォント/アクセントだけ注入する(背景衝突を防ぐ)。
        collab_body_class = f' collab-page collab--{aslug}' + (" cl-lp" if collab_lp else "")
        style_vars = ";".join(f"--cl-{k}:{v}" for k, v in tok.items())
        collab_body_attr = f' data-motif="{collab["motif"]}" style="{style_vars}"'
        collab_script = (f'<script src="/assets/js/collab-core.js?v={ASSET_V}" defer></script>'
                         f'<script src="/assets/js/collab-{aslug}.js?v={ASSET_V}" defer></script>')
    crumb_html = ""
    if crumbs:
        items = [('ホーム', '/')] + list(crumbs)
        lis = []
        for i, (label, href) in enumerate(items):
            if i == len(items) - 1 or not href:
                lis.append(f'<li><span aria-current="page">{esc(label)}</span></li>')
            else:
                lis.append(f'<li><a href="{href}">{esc(label)}</a></li>')
        crumb_html = f'<nav class="breadcrumb" aria-label="パンくずリスト"><div class="container container--wide"><ol>{"".join(lis)}</ol></div></nav>'

    html = f"""<!DOCTYPE html>
<html lang="ja" data-theme="{theme}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="theme-color" content="{'#0b0b10' if theme == 'dark' else '#fafafc'}">
<link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg">
{HEAD_FONTS}
<link rel="stylesheet" href="/assets/css/tokens.css?v={ASSET_V}">
<link rel="stylesheet" href="/assets/css/base.css?v={ASSET_V}">
<link rel="stylesheet" href="/assets/css/components.css?v={ASSET_V}">
<link rel="stylesheet" href="/assets/css/animations.css?v={ASSET_V}">
{collab_head}
</head>
<body class="page{url.rstrip('/').replace('/', '-') or '-home'}{collab_body_class}"{collab_body_attr}>
{header_html()}
{crumb_html}
<main id="main">
{body}
</main>
{footer_html()}
<script src="/assets/js/keys.js?v={ASSET_V}" defer></script>
<script src="/assets/js/fmt.js?v={ASSET_V}" defer></script>
<script src="/data/products.js?v={ASSET_V}" defer></script>
<script src="/assets/js/main.js?v={ASSET_V}" defer></script>
<script src="/assets/js/charts.js?v={ASSET_V}" defer></script>
<script src="/assets/js/store.js?v={ASSET_V}" defer></script>
<script src="/assets/js/biz.js?v={ASSET_V}" defer></script>
<script src="/assets/js/pages.js?v={ASSET_V}" defer></script>
<script src="/assets/js/auth-core.js?v={ASSET_V}" defer></script>
<script src="/assets/js/auth-guard.js?v={ASSET_V}" defer></script>
<script src="/assets/js/auth-account.js?v={ASSET_V}" defer></script>
<script src="/assets/js/auth-admin.js?v={ASSET_V}" defer></script>
<script src="/assets/js/auth-status.js?v={ASSET_V}" defer></script>
{collab_script}
</body>
</html>"""

    if url.endswith(".html"):
        out = ROOT / url.lstrip("/")
    elif url != "/":
        out = ROOT / url.strip("/") / "index.html"
    else:
        out = ROOT / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    if not noindex:
        PAGES.append({"url": url, "title": title, "desc": desc, "group": group})


# ==========================================================================
# 部品ビルダー
# ==========================================================================

def stats_html(stats, cols=4):
    cells = "".join(
        f"""<div class="stat"><p class="stat__value" data-count>{s['v']}<span class="unit">{s['u']}</span></p><p class="stat__label">{s['l']}</p></div>"""
        for s in stats)
    return f'<div class="stat-row reveal-stagger" style="--stat-cols:{cols}">{cells}</div>'


def sections_html(sections, glow="#e8442e", motif=None):
    out = []
    for i, sec in enumerate(sections):
        rev = " feature-split--rev" if i % 2 else ""
        pts = "".join(f"<li>{p}</li>" for p in sec.get("points", []))
        link = ""
        if sec.get("link"):
            link = f'<a class="link-arrow" href="{sec["link"][0]}">{sec["link"][1]}</a>'
        art = svg_art.svg_art(sec.get("art", "chip"), glow, motif=motif)
        out.append(f"""
<section class="section--sm">
  <div class="container">
    <div class="feature-split{rev}">
      <div class="feature-split__media reveal-scale">{art}</div>
      <div class="stack reveal">
        <p class="eyebrow">{sec['eyebrow']}</p>
        <h2 class="t-h2">{sec['title']}</h2>
        <p class="t-soft">{sec['body']}</p>
        <ul class="check-list">{pts}</ul>
        {link}
      </div>
    </div>
  </div>
</section>""")
    return "".join(out)


def spec_tables_html(specs):
    out = []
    for group, rows in specs:
        trs = "".join(f'<tr><th scope="row">{k}</th><td>{v}</td></tr>' for k, v in rows)
        out.append(f'<h3 class="spec-group-title">{group}</h3><div class="scroll-x"><table class="spec-table"><tbody>{trs}</tbody></table></div>')
    return "".join(out)


def product_card(p, show_price=True):
    line = LINES[p["line"]]
    badge = ""
    if p.get("flag") == "limited":
        badge = '<span class="badge badge--limited">数量限定</span>'
    elif p.get("flag") == "new":
        badge = '<span class="badge badge--new">NEW</span>'
    elif p["status"] == "old":
        badge = '<span class="badge badge--end">販売終了</span>'
    price = ""
    if show_price:
        price = (f'<p class="product-card__price">{yen(p["price"])} <small>(税込)〜</small></p>'
                 if p["status"] == "current" else '<p class="product-card__price t-faint">販売終了モデル</p>')
    url = product_url(p)
    return f"""<a class="product-card" href="{url}">
  <div class="product-card__media"><img src="{pimg(p['id'])}" alt="{esc(p['name'])}" loading="lazy" width="360" height="640"></div>
  <div class="product-card__body">
    <p class="product-card__tag">{line['label']} / {p['year']}</p>
    <p class="product-card__name">{esc(p['name'])} {badge}</p>
    <p class="product-card__copy">{esc(p['tagline'])}</p>
    {price}
  </div>
</a>"""


def product_url(p):
    seg = {"phone": "phone", "tablet": "tablet", "accessory": "accessories"}[p["cat"]]
    return f"/products/{seg}/{p['id']}/"


def cta_band(title, sub, buttons):
    btns = "".join(f'<a class="btn {cls}" href="{href}">{label}</a>' for label, href, cls in buttons)
    return f"""
<section class="section--sm">
  <div class="container">
    <div class="card card--flame t-center reveal" style="padding:clamp(40px,6vw,72px)">
      <h2 class="t-h2">{title}</h2>
      <p class="t-soft" style="max-width:560px;margin-inline:auto">{sub}</p>
      <div class="cluster cluster--center" style="margin-top:12px">{btns}</div>
    </div>
  </div>
</section>"""


# ==========================================================================
# 製品ページ
# ==========================================================================


def related_news_section(keywords, eyebrow="NEWSROOM", title="関連ニュース"):
    """キーワードに合致するニュース記事カード(最大3件)。合致なしなら空。"""
    hits = [n for n in NEWS if any(k and (k in n["title"] or k in n["excerpt"]) for k in keywords)][:3]
    if not hits:
        return ""
    cards = "".join(
        f'''<a class="card card--hover" href="/news/{n['id']}/">
<p class="t-micro t-faint">{n['date'].replace('-', '.')} <span class="badge" style="margin-left:8px">{n['cat']}</span></p>
<h3 class="t-h4">{esc(n['title'])}</h3>
<p class="t-small t-soft">{esc(n['excerpt'][:72])}…</p>
<p class="link-arrow">読む</p></a>'''
        for n in hits)
    return f'''
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">{eyebrow}</p><h2 class="t-h2">{title}</h2></div>
    <div class="grid grid--3 reveal-stagger">{cards}</div>
  </div>
</section>'''


def lineage_section(p):
    """同一ラインの系譜表(2世代以上あるデバイスのみ)。"""
    gens = sorted([x for x in ALL_PRODUCTS if x["cat"] == p["cat"] and x["line"] == p["line"]], key=lambda x: -x["year"])
    if len(gens) < 2:
        return ""
    rows = ""
    for g in gens:
        cur = g["id"] == p["id"]
        state = '<strong style="color:var(--accent)">現行</strong>' if g["status"] == "current" else '<span class="t-faint">販売終了</span>'
        name_cell = (f'<strong>{esc(g["name"])}(このページ)</strong>' if cur
                     else f'<a href="{product_url(g)}" style="color:var(--accent);font-weight:700">{esc(g["name"])}</a>')
        rows += (f'<tr><td>{name_cell}</td><td>{g["release"]}</td><td>{yen(g["price"])}</td>'
                 f'<td>{esc(get_spec(g, ["性能"], "SoC").split("(")[0])}</td><td>{state}</td></tr>')
    line = LINES[p["line"]]
    return f'''
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">LINEAGE</p><h2 class="t-h2">{line['label']}ラインの系譜</h2>
    <p class="t-soft t-small">初代から最新世代まで、このラインの歩みです。販売終了モデルのページもアーカイブとして公開しています。</p></div>
    <div class="scroll-x reveal"><table class="spec-table quick-table">
      <thead><tr><th scope="col">モデル</th><th scope="col">発売日</th><th scope="col">発売時価格</th><th scope="col">SoC</th><th scope="col">販売状況</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
  </div>
</section>'''


def cta_minimal(title, links):
    """カード帯を使わない軽い結び(技術ページ用 — 使い回し感の低減)。"""
    l = "".join(f'<a class="link-arrow" href="{h}">{txt}</a>' for txt, h in links)
    return (f'<section class="section--sm"><div class="container t-center" '
            f'style="display:grid;gap:16px;justify-items:center"><hr class="divider" style="width:min(320px,60%)">' 
            f'<h2 class="t-h3">{title}</h2><div class="cluster cluster--center" style="gap:26px">{l}</div></div></section>')


def build_product_page(p):
    line = LINES[p["line"]]
    glow = p.get("glow") or line["glow"]
    url = product_url(p)
    is_device = p["cat"] in ("phone", "tablet")
    # コラボ製品はセクション図版にも作品意匠(motif)を引き継ぐ
    p_motif = p.get("collab")
    cat_label = {"phone": "スマートフォン", "tablet": "タブレット", "accessory": "アクセサリ"}[p["cat"]]
    cat_url = {"phone": "/products/phone/", "tablet": "/products/tablet/", "accessory": "/products/accessories/"}[p["cat"]]

    # --- 購入モジュール ---
    swatches = "".join(
        f'<button type="button" class="swatch{" is-active" if i == 0 else ""}" data-color-index="{i}" style="--swatch:{c["hex"]}" aria-label="{esc(c["name"])}" title="{esc(c["name"])}"></button>'
        for i, c in enumerate(p["colors"]))
    storages = "".join(f"""
      <label class="choice">
        <input type="radio" name="storage" value="{i}" {"checked" if i == 0 else ""}>
        <span class="choice__radio"></span>
        <span class="choice__body"><span class="choice__title">{esc(s['label'])}</span></span>
        <span class="choice__price">{yen(p['price'] + s['delta'])}</span>
      </label>""" for i, s in enumerate(p["storage"])) if p["storage"] else ""

    # カメラ構成オプション(法人機など)。選択で購入画像がカメラレス背面に切り替わる
    camopts = "".join(f"""
      <label class="choice">
        <input type="radio" name="camopt" value="{i}" {"checked" if i == 0 else ""}>
        <span class="choice__radio"></span>
        <span class="choice__body"><span class="choice__title">{esc(o['label'])}</span>
        <span class="choice__sub t-micro t-faint">{esc(o.get('note', ''))}</span></span>
        <span class="choice__price">{('+' + yen(o['delta'])) if o.get('delta') else '±¥0'}</span>
      </label>""" for i, o in enumerate(p.get("camera_options", []))) if p.get("camera_options") else ""

    if p["status"] == "current":
        buy_actions = f"""
        <p class="buy-price"><span id="buyPrice">{yen(p['price'])}</span> <small class="t-faint">(税込)</small></p>
        <p class="t-micro t-faint">分割払い(24回)例: 月々 {yen(round(p['price'] / 24 // 10 * 10))} 〜 / 5,000円以上で送料無料</p>
        <div class="cluster">
          <button class="btn btn--primary btn--lg" id="addToCart">カートに追加</button>
          {'<a class="btn btn--ghost btn--lg" href="' + url + 'specs/">スペックを見る</a>' if is_device else ''}
        </div>"""
    else:
        newest = [x for x in ALL_PRODUCTS if x["line"] == p["line"] and x["status"] == "current"]
        alt = f'<a class="btn btn--primary" href="{product_url(newest[0])}">現行モデル {esc(newest[0]["name"])} を見る</a>' if newest else ""
        buy_actions = f"""
        <div class="notice"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4l9 16H3z"/><path d="M12 10.5v4M12 17.6h.01"/></svg> {esc(p['name'])} は販売を終了しました。仕様の記録としてページを公開しています。</div>
        <div class="cluster">{alt}
          {'<a class="btn btn--ghost" href="' + url + 'specs/">スペックを見る</a>' if is_device else ''}
        </div>"""

    color_names = " / ".join(c["name"] for c in p["colors"])
    buy_box = f"""
<section class="section--sm" id="buy">
  <div class="container">
    <div class="buy-grid" data-product="{p['id']}">
      <div class="buy-media reveal-l">
        <img id="buyImage" src="{pimg(p['id'])}" alt="{esc(p['name'])}" width="360" height="640">
        {f'''<div class="buy-view" role="group" aria-label="表示切替">
          <button type="button" class="buy-view__btn is-active" data-buyview="back" aria-pressed="true">背面</button>
          <button type="button" class="buy-view__btn" data-buyview="front" data-front-src="{pimg_front(p['id'])}" aria-pressed="false">正面</button>
        </div>''' if is_device else ''}
      </div>
      <div class="stack reveal-r">
        <p class="eyebrow">{line['label']}</p>
        <h2 class="t-h3">{esc(p['name'])} を構成する</h2>
        <div class="field"><label>カラー — <span id="colorName">{esc(p['colors'][0]['name'])}</span>(全{len(p['colors'])}色: {esc(color_names)})</label>
          <div class="cluster">{swatches}</div></div>
        {'<div class="field"><label>メモリとストレージ</label><div class="choice-grid">' + storages + '</div></div>' if storages else ''}
        {'<div class="field"><label>カメラ構成</label><div class="choice-grid">' + camopts + '</div></div>' if camopts else ''}
        {buy_actions}
        <p class="t-micro t-faint">発売日: {p['release']} / 型番: SZ-{p['id'].upper().replace('-', '')}</p>
      </div>
    </div>
  </div>
</section>"""

    # --- 関連製品 ---
    same_line = [x for x in ALL_PRODUCTS if x["line"] == p["line"] and x["id"] != p["id"]]
    cross = []
    if p["cat"] == "phone":
        cross = [x for x in ACCESSORIES if x["status"] == "current"][:3]
    elif p["cat"] == "tablet":
        cross = [x for x in ACCESSORIES if x["id"] in ("grip-pro", "buds", "raisoku-charger")]
    related_cards = "".join(product_card(x) for x in (same_line[:3] + cross[: max(0, 3 - len(same_line))]))
    related = f"""
<section class="section section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">RELATED</p><h2 class="t-h2">あわせて見たい製品</h2></div>
    <div class="grid grid--3 grid--cards reveal-stagger">{related_cards}</div>
  </div>
</section>""" if related_cards else ""

    chip_link = ""
    if p.get("chip"):
        # コラボ専用SoC(例 gensoro-e1)は専用シリコンページへリンクする
        if p.get("collab"):
            soc_name = get_spec(p, ["性能"], "SoC").split("(")[0].strip()
            chip_link = f'<a class="btn btn--ghost" href="/collab/{p["collab"]}/silicon/soc/">専用SoC {esc(soc_name)} を見る</a>'
            chip = None
        else:
            chip = next((t for t in TECHS if t["id"] == p["chip"]), None)
            if chip:
                chip_link = f'<a class="btn btn--ghost" href="/tech/cpu/{p["chip"]}/">搭載SoC {esc(chip["name"])} を見る</a>'

    # --- データセクション(グラフ+表) ---
    data_section = ""
    if is_device:
        gens = sorted([x for x in ALL_PRODUCTS if x["cat"] == p["cat"] and x["line"] == p["line"]], key=lambda x: x["year"])
        g_labels = [f"{x['name']}({x['year']})" for x in gens]
        antutu_vals = [product_antutu(x) or 0 for x in gens]
        bat_vals = [num(get_spec(x, ["バッテリー"], "バッテリー容量")) for x in gens]
        hi = next(i for i, x in enumerate(gens) if x["id"] == p["id"])
        charts_html = ""
        if len(gens) >= 2 and all(antutu_vals):
            charts_html += chart({"type": "bar", "title": f"{line['label']}ライン — AnTuTuスコアの世代比較", "unit": "万点",
                                  "labels": g_labels, "values": antutu_vals, "highlight": hi})
        if len(gens) >= 2 and all(bat_vals):
            charts_html += chart({"type": "bar", "title": "バッテリー容量の世代推移", "unit": "mAh",
                                  "labels": g_labels, "values": bat_vals, "highlight": hi})
        charts_html += chart({"type": "radar", "title": f"{p['name']} 性能バランス(5軸・当社評価)",
                              "axes": RADAR_AXES, "series": [{"name": p["name"], "values": radar_values(p)}]})
        data_section = f"""
<section class="section--sm" id="data">
  <div class="container">
    <div class="section-head"><p class="eyebrow">DATA</p><h2 class="t-h2">数字は、嘘をつかない。</h2>
    <p class="t-soft t-small">スコア・容量は当社測定条件による参考値です。完全な仕様は<a href="{url}specs/" style="color:var(--accent);text-decoration:underline">スペックページ</a>へ。</p></div>
    <div class="chart-grid">{charts_html}</div>
  </div>
</section>"""
        # ラインの性格を構成に反映する固有セクション
        if p["line"] in GAMING_LINES:
            data_section += game_fps_section(p)
        elif p["line"] in LIFE_LINES:
            data_section += battery_life_section(p)
    elif p["id"] in ACC_CHARTS:
        # アクセサリ: 製品ごとに異なる比較グラフ
        data_section = f"""
<section class="section--sm" id="data">
  <div class="container">
    <div class="section-head"><p class="eyebrow">DATA</p><h2 class="t-h2">数字で見る、{esc(p['name'])}。</h2></div>
    <div class="chart-grid">{chart(ACC_CHARTS[p['id']])}</div>
    <p class="t-micro t-faint" style="margin-top:14px">当社試験条件による参考値です。比較対象は市場の一般的な製品カテゴリの代表値。</p>
  </div>
</section>"""

    # --- 全幅ビジュアルブレイク ---
    bleed_claims = {
        "suzaku": "勝敗を分ける0.01秒のために。",
        "neo": "価格のために、性能は捨てない。",
        "tsubame": "テクノロジーは、そっと寄り添うもの。",
        "lite": "良いものは、高くなくていい。",
        "pad": "大画面は、没入の別名だ。",
        "pad-neo": "どこへでも、戦場を持ち出せ。",
        "t-pad": "家族の時間の、真ん中に。",
        "t-pad-lite": "気軽さこそ、最強の機能。",
    }
    bleed = ""
    if is_device:
        bleed = f"""
<section class="full-bleed" style="--bleed-glow:{glow}59">
  <p class="eyebrow eyebrow--center" style="justify-content:center">{esc(p['kana'])} / {p['year']}</p>
  <h2 class="reveal-scale reveal">{esc(bleed_claims.get(p['line'], p['tagline']))}</h2>
</section>"""

    # --- 同梱物 + 製品FAQ + 対応アクセサリ + サポート ---
    box_html = "".join(f"<li>{esc(x)}</li>" for x in box_items(p))
    faq_items = LINE_FAQ.get(p["line"], LINE_FAQ["acc"])
    faq_html = "".join(
        f'<div class="accordion__item"><button class="accordion__q" aria-expanded="false"><span>{esc(q)}</span></button>'
        f'<div class="accordion__a"><div class="accordion__a-inner"><div class="accordion__a-body"><p>{a}</p></div></div></div></div>'
        for q, a in faq_items)
    extras = f"""
<div class="band-light" data-theme="light">
<section class="section--sm">
  <div class="container">
    <div class="feature-split" style="align-items:start">
      <div class="stack reveal">
        <p class="eyebrow">IN THE BOX</p>
        <h2 class="t-h2">同梱物</h2>
        <ul class="check-list">{box_html}</ul>
        <p class="t-micro t-faint">パッケージはプラスチック使用量を98%削減した再生紙製です。<a href="/sustainability/" style="color:var(--accent)">環境への取り組み</a></p>
      </div>
      <div class="stack reveal">
        <p class="eyebrow">Q&amp;A</p>
        <h2 class="t-h2">よくある質問</h2>
        <div class="accordion">{faq_html}</div>
        <a class="link-arrow" href="/support/faq/">すべてのFAQを見る</a>
      </div>
    </div>
  </div>
</section>"""
    if is_device:
        extras += f"""
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">ACCESSORIES</p><h2 class="t-h2">{esc(p['name'])} で使える純正アクセサリ</h2></div>
    {acc_compat_table(p)}
  </div>
</section>"""
    extras += """
<section class="section--sm">
  <div class="container">
    <div class="grid grid--3 reveal-stagger">
      <a class="card card--hover" href="/support/warranty/">
        <div class="card__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l7 4v5c0 4.5-3 8-7 9-4-1-7-4.5-7-9V7z"/><path d="M9.5 12l2 2 3.5-4"/></svg></div>
        <h3 class="t-h4">1年保証 + SUZAKU Care+</h3><p class="t-small t-soft">標準で1年間のメーカー保証。Care+なら落下・水濡れもカバー。</p><p class="link-arrow">保証を見る</p></a>
      <a class="card card--hover" href="/support/repair/">
        <div class="card__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 6.5a4 4 0 0 0-5.6 5L4 16.4V20h3.6l4.9-4.9a4 4 0 0 0 5-5.6L15 12l-3-3z"/></svg></div>
        <h3 class="t-h4">最短即日修理</h3><p class="t-small t-soft">秋葉原サービスセンターで画面・電池交換は即日。配送修理も5〜7営業日。</p><p class="link-arrow">修理を申し込む</p></a>
      <a class="card card--hover" href="/sustainability/recycle/">
        <div class="card__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21c-5 0-8-3.5-8-8 0-5.5 4.5-9.5 8-10 3.5.5 8 4.5 8 10 0 4.5-3 8-8 8z"/><path d="M12 21c2-3 3-6.5 3-10"/></svg></div>
        <h3 class="t-h4">使い終わったら無償回収</h3><p class="t-small t-soft">古い端末はメーカー問わず無償回収。資源の96%を再利用します。</p><p class="link-arrow">回収について</p></a>
    </div>
  </div>
</section>
</div>"""

    # --- カラーギャラリー(2色以上のデバイス) ---
    color_gallery = ""
    if is_device and len(p["colors"]) >= 2:
        gcards = f"""<figure class="color-card reveal"><img src="{pimg_front(p['id'])}" alt="{esc(p['name'])} 正面ディスプレイ" loading="lazy" width="360" height="640"><figcaption><i style="--swatch:var(--accent)"></i>正面ディスプレイ</figcaption></figure>"""
        gcards += "".join(
            f"""<figure class="color-card reveal"><img src="{pimg(p['id'], i)}" alt="{esc(p['name'])} {esc(c['name'])}" loading="lazy" width="360" height="640"><figcaption><i style="--swatch:{c['hex']}"></i>{esc(c['name'])}</figcaption></figure>"""
            for i, c in enumerate(p["colors"]))
        color_gallery = f"""
<section class="section--sm" id="colors">
  <div class="container">
    <div class="section-head"><p class="eyebrow">COLORS &amp; DISPLAY</p><h2 class="t-h2">{len(p['colors'])}つの色。どれも、{esc(p['kana'].split(' ')[0])}。</h2></div>
    <div class="color-gallery">{gcards}</div>
    {'<div class="cluster" style="margin-top:20px"><a class="btn btn--primary" href="#buy">カラーを選んで購入する</a></div>' if p['status'] == 'current' else ''}
  </div>
</section>"""

    # --- ローカルナビ(Apple式・PCのみ表示) ---
    local_links = '<a href="#buy">構成と価格</a>' if p["status"] == "current" else ""
    if is_device:
        local_links += '<a href="#data">性能データ</a>'
        if len(p["colors"]) >= 2:
            local_links += '<a href="#colors">カラー</a>'
        local_links += f'<a href="{url}specs/">仕様</a>'
    local_links += '<a href="/products/compare/">比較</a>'
    local_cta = (f'<span class="localnav__price">{yen(p["price"])}〜</span><a class="btn btn--primary btn--sm" href="#buy">購入へ</a>'
                 if p["status"] == "current" else '<span class="badge badge--end">販売終了</span>')
    localnav = f"""
<div class="localnav" id="localnav" aria-hidden="true">
  <div class="localnav__inner">
    <span class="localnav__name">{esc(p['name'])}</span>
    <nav class="localnav__links" aria-label="{esc(p['name'])}内のセクション">{local_links}</nav>
    {local_cta}
  </div>
</div>"""

    # --- 注記(Apple式footnotes) ---
    note_items = [
        "価格はすべて消費税込みの当社直販価格です。分割払いの月額は24回均等払いの概算で、手数料はカード会社の規定によります。",
        "バッテリー駆動時間は輝度50%・Wi-Fi接続・当社試験環境での測定値です。使用状況・経年により変動します。",
        "ベンチマークスコア・温度・fpsは室温25℃の当社試験環境での測定値であり、性能を保証するものではありません。",
    ]
    if p["line"] in GAMING_LINES:
        note_items.append("実測パフォーマンスの検証タイトルは実在のゲームではなく、当社のベンチマーク用シナリオです。ファン動作音は無響室での測定値です。")
    if is_device:
        note_items.append("防塵防水性能は当社試験条件によるもので、無故障・無破損を保証するものではありません。水没・砂塵環境でのご使用はお避けください。")
    note_items.append("本サイトは架空企業のデモンストレーションであり、記載のすべての製品・数値はフィクションです。")
    footnotes = ('<section class="section--sm"><div class="container container--narrow">'
                 '<hr class="divider" style="margin-bottom:22px"><ol class="footnotes">'
                 + "".join(f"<li>{n}</li>" for n in note_items) + "</ol></div></section>")

    # --- フローティング購入バー(現行モデルのみ) ---
    buy_float = ""
    if p["status"] == "current":
        buy_float = f"""
<div class="buy-float" id="buyFloat" aria-hidden="true">
  <div class="buy-float__inner">
    <img src="{pimg(p['id'])}" alt="" width="36" height="52" style="height:44px;width:auto">
    <div>
      <p class="buy-float__name">{esc(p['name'])}</p>
      <p class="buy-float__price">{yen(p['price'])}(税込)〜</p>
    </div>
    <a class="btn btn--primary btn--sm" href="#buy">購入へ</a>
  </div>
</div>"""

    body = f"""
<section class="hero hero--sub" style="--line-glow:{glow}">
  <div class="hero__bg hero__bg--glow" style="background:
    radial-gradient(52% 42% at 50% 66%, {glow}44, transparent 70%),
    radial-gradient(40% 32% at 80% 12%, rgba(217,164,65,0.08), transparent 70%),
    var(--bg-deep)"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">{line['label']} — {p['year']}</p>
    <h1 class="t-hero">{esc(p['name'])}</h1>
    <p class="t-lead" style="max-width:640px">{esc(p['tagline'])}<br><span class="t-small">{esc(p['sub'])}</span></p>
    <div class="hero__actions">
      {'<a class="btn btn--primary btn--lg" href="#buy">' + yen(p['price']) + '(税込)〜 購入へ</a>' if p['status'] == 'current' else '<span class="badge badge--end">販売終了モデル</span>'}
      {chip_link}
    </div>
    {f'<img class="hero-device" src="{pimg(p["id"])}" alt="{esc(p["name"])}" width="340" height="600">' if is_device else ''}
  </div>
</section>
<section class="section--sm"><div class="container">{stats_html(p['stats'])}</div></section>
{buy_box}
{bleed}
{color_gallery}
{sections_html(p['sections'], glow, p_motif)}
{data_section}
{lineage_section(p) if is_device else ''}
{extras}
{f'''<section class="section--sm"><div class="container"><div class="card t-center" style="padding:clamp(32px,5vw,56px)"><h2 class="t-h3">すべての仕様を確認する</h2><p class="t-soft">サイズ・性能・カメラ・通信仕様の完全なリストをご用意しています。</p><div class="cluster cluster--center"><a class="btn btn--primary" href="{url}specs/">{esc(p['name'])} の仕様を見る</a><a class="btn btn--ghost" href="/products/compare/">他のモデルと比較する</a></div></div></div></section>''' if is_device else ''}
{related}
{related_news_section([p['name']], title=f"{esc(p['name'])} のニュース")}
{cta_band(*(
    ('次の勝利は、ストアから。', '全国送料無料。氷嵐クーラーやGrip Proとの同時購入で、装備を一気にそろえられます。')
    if p['line'] in GAMING_LINES else
    ('毎日の相棒を、ストアで。', '全国送料無料(5,000円以上)。14日間の返品保証と1年間のメーカー保証付き。')
    if p['line'] in LIFE_LINES else
    ('本体と、そろえて。', 'ストアなら本体とアクセサリをまとめて一度に受け取れます。5,000円以上で送料無料。')
), [('ストアで見る', '/store/', 'btn--primary'), ('購入ガイド', '/store/guide/', 'btn--ghost')])}
{footnotes}
{localnav}
{buy_float}
"""
    crumbs = [("製品", "/products/"), (cat_label, cat_url), (p["name"], None)]
    collab_cfg = collab_by_slug(p["collab"]) if p.get("collab") else None
    render_page(url, f"{p['name']} — {p['tagline']}", p["sub"], body, "dark", crumbs, "製品",
                layout="collab" if collab_cfg else None, collab=collab_cfg, collab_lp=False)

    # --- specsページ(スマホ・タブレットのみ) ---
    if is_device:
        spec_body = f"""
<section class="hero hero--page">
  <div class="hero__inner hero-enter">
    <p class="eyebrow">{line['label']}</p>
    <h1 class="t-h1">{esc(p['name'])} — 仕様</h1>
    <p class="t-soft">発売日: {p['release']} / {'税込 ' + yen(p['price']) + '〜' if p['status'] == 'current' else '販売終了'}</p>
    <div class="cluster">
      <a class="btn btn--primary" href="{url}#buy">{'購入ページへ' if p['status'] == 'current' else '製品ページへ'}</a>
      <a class="btn btn--ghost" href="/products/compare/">比較する</a>
    </div>
  </div>
</section>
<section class="section--sm"><div class="container container--narrow reveal">{spec_tables_html(p['specs'])}
<p class="t-micro t-faint" style="margin-top:28px">記載の数値は当社測定条件による設計値です。使用環境により変動する場合があります。バッテリー持続時間は輝度50%・Wi-Fi接続時の当社試験値です。</p>
</div></section>
{cta_band('この仕様を、あなたの手に。', 'SUZAKU ストアなら全モデル送料無料でお届けします。', [('ストアで見る', '/store/', 'btn--primary'), (p['name'] + ' 製品ページ', url, 'btn--ghost')])}
"""
        render_page(url + "specs/", f"{p['name']} 仕様", f"{p['name']}の詳細スペック一覧。サイズ、性能、ディスプレイ、カメラ、バッテリー、通信仕様。",
                    spec_body, "dark", crumbs[:-1] + [(p["name"], url), ("仕様", None)], "製品",
                    layout="collab" if collab_cfg else None, collab=collab_cfg, collab_lp=False)


# ==========================================================================
# 法人向け(一般ラインと完全分離・/business/ 配下)
# ==========================================================================

BIZ_GLOW = "#4a7ac8"


def biz_url(p):
    return f"/business/{p['id']}/"


def biz_buy_module(p):
    """法人機の構成プレビュー(色/容量/カメラ+背面正面トグル)。カートではなく見積導線。
    store.js の .buy-grid[data-product] とは衝突しないよう data-biz 属性で分離し、biz.js が制御する。"""
    swatches = "".join(
        f'<button type="button" class="swatch{" is-active" if i == 0 else ""}" data-color-index="{i}" '
        f'aria-pressed="{"true" if i == 0 else "false"}" style="--swatch:{c["hex"]}" '
        f'aria-label="{esc(c["name"])}" title="{esc(c["name"])}"></button>'
        for i, c in enumerate(p["colors"]))
    storages = "".join(f"""
      <label class="choice">
        <input type="radio" name="bizstorage" value="{i}" data-delta="{s['delta']}" {"checked" if i == 0 else ""}>
        <span class="choice__radio"></span>
        <span class="choice__body"><span class="choice__title">{esc(s['label'])}</span></span>
        <span class="choice__price">{yen(p['price'] + s['delta'])}</span>
      </label>""" for i, s in enumerate(p["storage"]))
    camopts = "".join(f"""
      <label class="choice">
        <input type="radio" name="bizcam" value="{i}" {"checked" if i == 0 else ""}>
        <span class="choice__radio"></span>
        <span class="choice__body"><span class="choice__title">{esc(o['label'])}</span>
        <span class="choice__sub t-micro t-faint">{esc(o.get('note', ''))}</span></span>
        <span class="choice__price">{('+' + yen(o['delta'])) if o.get('delta') else '±¥0'}</span>
      </label>""" for i, o in enumerate(p.get("camera_options", [])))
    color_names = " / ".join(c["name"] for c in p["colors"])
    return f"""
<section class="section--sm" id="config">
  <div class="container">
    <div class="buy-grid" data-biz="{p['id']}" data-base="{p['price']}" data-v="{ASSET_V}">
      <div class="buy-media reveal-l">
        <img id="bizImage" src="{pimg(p['id'])}" alt="{esc(p['name'])}" width="360" height="640">
        <div class="buy-view" role="group" aria-label="表示切替">
          <button type="button" class="buy-view__btn is-active" data-bizview="back" aria-pressed="true">背面</button>
          <button type="button" class="buy-view__btn" data-bizview="front" data-front-src="{pimg_front(p['id'])}" data-front-nc-src="/assets/img/products/{p['id']}-nc-front.svg?v={ASSET_V}" aria-pressed="false">正面</button>
        </div>
      </div>
      <div class="stack reveal-r">
        <p class="eyebrow">法人専用モデル — お見積り</p>
        <h2 class="t-h3">{esc(p['name'])} を構成する</h2>
        <div class="field"><label>カラー — <span id="bizColorName">{esc(p['colors'][0]['name'])}</span>(全{len(p['colors'])}色: {esc(color_names)})</label>
          <div class="cluster">{swatches}</div></div>
        <div class="field"><label>メモリとストレージ</label><div class="choice-grid">{storages}</div></div>
        <div class="field"><label>カメラ構成</label><div class="choice-grid">{camopts}</div></div>
        <p class="buy-price"><span id="bizPrice">{yen(p['price'])}</span> <small class="t-faint">〜(税別・法人参考価格)</small></p>
        <div class="cluster">
          <a class="btn btn--primary btn--lg" href="/business/store/">導入のご相談・お見積り</a>
          <a class="btn btn--ghost btn--lg" href="{biz_url(p)}specs/">仕様を見る</a>
        </div>
        <p class="t-micro t-faint">法人契約(MDM・保守)前提のモデルです。個人向けの単体販売は行っていません。数量・構成に応じたお見積りは法人窓口で承ります。</p>
      </div>
    </div>
  </div>
</section>"""


def biz_os_callout():
    return f"""
<section class="section--sm"><div class="container">
  <div class="feature-split">
    <div class="feature-split__media reveal-scale">{svg_art.svg_art('shield', BIZ_GLOW)}</div>
    <div class="stack reveal">
      <p class="eyebrow">{esc(BIZ_OS['name'])}</p>
      <h2 class="t-h2">{esc(BIZ_OS['tagline'])}</h2>
      <p class="t-soft">{esc(BIZ_OS['lead'])}</p>
      <a class="link-arrow" href="/business/os/">法人専用OSの詳細を見る</a>
    </div>
  </div>
</div></section>"""


def build_biz_product_page(p):
    """法人専用モデルのページ(/business/{id}/)。一般の build_product_page とは分離し、
    カートではなく見積・導入相談へ誘導する。カメラ構成トグルは biz.js が担当。"""
    line = LINES[p["line"]]
    glow = p.get("glow") or line["glow"]
    url = biz_url(p)
    body = f"""
<section class="hero hero--sub" style="--line-glow:{glow}">
  <div class="hero__bg hero__bg--glow" style="background:
    radial-gradient(52% 42% at 50% 66%, {glow}44, transparent 70%),
    var(--bg-deep)"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">{line['label']} — 法人専用</p>
    <h1 class="t-hero">{esc(p['name'])}</h1>
    <p class="t-lead" style="max-width:640px">{esc(p['tagline'])}<br><span class="t-small">{esc(p['sub'])}</span></p>
    <div class="hero__actions">
      <a class="btn btn--primary btn--lg" href="#config">構成とお見積り</a>
      <a class="btn btn--ghost btn--lg" href="/business/os/">法人専用OSを見る</a>
    </div>
    <img class="hero-device" src="{pimg(p['id'])}" alt="{esc(p['name'])}" width="340" height="600">
  </div>
</section>
<section class="section--sm"><div class="container">{stats_html(p['stats'])}</div></section>
{biz_buy_module(p)}
{sections_html(p['sections'], glow)}
{biz_os_callout()}
<section class="section--sm"><div class="container"><div class="card t-center" style="padding:clamp(32px,5vw,56px)">
  <h2 class="t-h3">すべての仕様を確認する</h2>
  <p class="t-soft">サイズ・性能・カメラ・法人機能・通信仕様の完全なリストをご用意しています。</p>
  <div class="cluster cluster--center"><a class="btn btn--primary" href="{url}specs/">{esc(p['name'])} の仕様を見る</a><a class="btn btn--ghost" href="/business/store/">法人向けストアへ</a></div>
</div></div></section>
{cta_band('導入は、お見積りから。', 'MDMキッティング・ボリュームディスカウント・引取交換保守まで、法人窓口が一括でご案内します。', [('導入のご相談・お見積り', '/business/store/', 'btn--primary'), ('法人お問い合わせ', '/business/contact/', 'btn--ghost')])}
"""
    crumbs = [("法人のお客様", "/business/"), (p["name"], None)]
    render_page(url, f"{p['name']} — {p['tagline']}", p["sub"], body, "dark", crumbs, "法人")

    spec_body = f"""
<section class="hero hero--page">
  <div class="hero__inner hero-enter">
    <p class="eyebrow">{line['label']} — 法人専用</p>
    <h1 class="t-h1">{esc(p['name'])} — 仕様</h1>
    <p class="t-soft">発売日: {p['release']} / 法人参考価格 税別 {yen(p['price'])}〜</p>
    <div class="cluster">
      <a class="btn btn--primary" href="{url}#config">構成とお見積り</a>
      <a class="btn btn--ghost" href="/business/store/">法人向けストア</a>
    </div>
  </div>
</section>
<section class="section--sm"><div class="container container--narrow reveal">{spec_tables_html(p['specs'])}
<p class="t-micro t-faint" style="margin-top:28px">記載の数値は当社測定条件による設計値です。本サイトは架空企業のデモであり、記載のすべての製品・数値はフィクションです。</p>
</div></section>
{cta_band('この一台を、組織の標準に。', '台数・構成に応じたお見積りを法人窓口で承ります。', [('導入のご相談・お見積り', '/business/store/', 'btn--primary'), (p['name'] + ' 製品ページ', url, 'btn--ghost')])}
"""
    render_page(url + "specs/", f"{p['name']} 仕様", f"{p['name']}の詳細スペック一覧。サイズ、性能、カメラ、法人機能、通信仕様。",
                spec_body, "dark", crumbs[:-1] + [(p["name"], url), ("仕様", None)], "法人")


def build_biz_os_page():
    """法人専用OSの説明ページ(/business/os/)。BIZ_OS(単一ソース)から生成。"""
    glow = BIZ_GLOW
    feats = "".join(
        f'<article class="card reveal"><h3 class="t-h4">{esc(f["title"])}</h3>'
        f'<p class="t-small t-soft">{esc(f["body"])}</p></article>'
        for f in BIZ_OS["features"])
    faq = "".join(
        f'<div class="accordion__item"><button class="accordion__q" aria-expanded="false"><span>{esc(q)}</span></button>'
        f'<div class="accordion__a"><div class="accordion__a-inner"><div class="accordion__a-body"><p>{a}</p></div></div></div></div>'
        for q, a in BIZ_OS["faq"])
    body = f"""
<section class="hero hero--sub" style="--line-glow:{glow}">
  <div class="hero__bg hero__bg--glow" style="background:radial-gradient(52% 42% at 50% 66%, {glow}44, transparent 70%), var(--bg-deep)"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">{esc(BIZ_OS['short'])} — {esc(BIZ_OS['base'])}</p>
    <h1 class="t-hero">{esc(BIZ_OS['name'])}</h1>
    <p class="t-lead" style="max-width:660px">{esc(BIZ_OS['tagline'])}<br><span class="t-small">{esc(BIZ_OS['lead'])}</span></p>
    <div class="hero__actions">
      <a class="btn btn--primary btn--lg" href="/business/kaname-b1/">搭載モデル KANAME B1</a>
      <a class="btn btn--ghost btn--lg" href="/business/store/">導入のご相談</a>
    </div>
  </div>
</section>
<section class="section--sm"><div class="container">{stats_html(BIZ_OS['stats'])}</div></section>
<section class="section--sm"><div class="container">
  <div class="section-head"><p class="eyebrow">FEATURES</p><h2 class="t-h2">管理・セキュリティ・長期運用</h2>
  <p class="t-soft">情報システム部門が「配って、守って、長く使う」ための機能だけを残しました。</p></div>
  <div class="grid grid--3 reveal-stagger">{feats}</div>
</div></section>
<div class="band-light" data-theme="light"><section class="section--sm"><div class="container container--narrow">
  <div class="section-head"><p class="eyebrow">Q&amp;A</p><h2 class="t-h2">よくある質問</h2></div>
  <div class="accordion">{faq}</div>
</div></section></div>
{cta_band('OSも、一般とは分けて。', '法人専用エディションの詳細・検証端末のご相談は法人窓口へ。', [('導入のご相談・お見積り', '/business/store/', 'btn--primary'), ('法人お問い合わせ', '/business/contact/', 'btn--ghost')])}
<section class="section--sm"><div class="container container--narrow"><p class="t-micro t-faint">{esc(BIZ_OS['note'])}</p></div></section>
"""
    render_page("/business/os/", f"{BIZ_OS['name']} — 法人専用OS", BIZ_OS["lead"],
                body, "dark", [("法人のお客様", "/business/"), ("法人専用OS", None)], "法人")


def biz_store_card(p):
    cam = "標準 / カメラレス(セキュア仕様)構成を選択可" if p.get("camera_options") else ""
    return f"""<a class="product-card" href="{biz_url(p)}">
  <div class="product-card__media"><img src="{pimg(p['id'])}" alt="{esc(p['name'])}" loading="lazy" width="360" height="640"></div>
  <div class="product-card__body">
    <p class="product-card__tag">{LINES[p['line']]['label']} / 法人専用</p>
    <h3 class="product-card__name">{esc(p['name'])}</h3>
    <p class="product-card__desc t-small t-soft">{esc(p['sub'])}</p>
    <p class="product-card__price">税別 {yen(p['price'])} <small>(法人参考価格)〜</small></p>
    <p class="t-micro t-faint">{esc(cam)}</p>
    <p class="link-arrow">構成とお見積り</p>
  </div>
</a>"""


def build_biz_store():
    """法人向けストア(/business/store/)。一般ストアのカートとは分離し、見積・導入相談フロー。"""
    cards = "".join(biz_store_card(p) for p in BIZ_PRODUCTS)
    steps = [
        ("01", "ご相談", "台数・利用シーン・MDM環境をお聞かせください。撮影禁止区域向けのカメラレス構成の要否もこの段階で伺います。"),
        ("02", "お見積り", "構成・数量・保守条件に応じたお見積りをご提示します。ボリュームディスカウント・リースのご相談も承ります。"),
        ("03", "キッティング納品", "ゼロタッチ登録でMDMプロファイルを事前適用し、開梱後すぐ使える状態でお届け。資産管理ラベルも同梱します。"),
    ]
    flow = "".join(
        f'<div class="card reveal"><p class="stat__value" style="color:var(--accent)">{n}</p>'
        f'<h3 class="t-h4">{esc(t)}</h3><p class="t-small t-soft">{esc(d)}</p></div>'
        for n, t, d in steps)
    body = f"""
<section class="hero hero--sub" style="--line-glow:{BIZ_GLOW}">
  <div class="hero__bg hero__bg--glow"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">BUSINESS STORE</p>
    <h1 class="t-hero">法人向けストア</h1>
    <p class="t-lead" style="max-width:660px">法人専用モデルの導入は、カート購入ではなくお見積り・ご相談から。台数・構成・保守条件に合わせてご案内します。</p>
  </div>
</section>
<section class="section--sm"><div class="container">
  <div class="section-head"><p class="eyebrow">LINEUP</p><h2 class="t-h2">法人専用ラインアップ</h2></div>
  <div class="grid grid--3 grid--cards reveal-stagger">{cards}</div>
</div></section>
<section class="section--sm"><div class="container">
  <div class="section-head"><p class="eyebrow">HOW IT WORKS</p><h2 class="t-h2">導入の流れ</h2>
  <p class="t-soft">ご相談から納品まで、法人窓口が一括でご案内します。</p></div>
  <div class="grid grid--3 reveal-stagger">{flow}</div>
</div></section>
{cta_band('まずは、ご相談から。', '導入台数が1台からでもご相談いただけます。お見積り・検証機貸出のご依頼はこちらへ。', [('法人お問い合わせ', '/business/contact/', 'btn--primary'), ('法人ソリューション', '/business/solutions/', 'btn--ghost')])}
<section class="section--sm"><div class="container container--narrow"><p class="t-micro t-faint">本サイトは架空企業のデモであり、記載のすべての製品・価格・サービスはフィクションです。実際の販売・見積は行っていません。</p></div></section>
"""
    render_page("/business/store/", "法人向けストア — 導入のご相談・お見積り",
                "法人専用モデルの導入相談・お見積り。KANAME B1 の構成、MDMキッティング、保守までワンストップでご案内します。",
                body, "dark", [("法人のお客様", "/business/"), ("法人向けストア", None)], "法人")


# ==========================================================================
# 技術ページ
# ==========================================================================

TECH_HUBS = {
    "cpu": {"title": "雷 RAI", "en": "CPU / SoC", "path": "/tech/cpu/",
            "desc": "自社SoCシリーズ「雷」。旗艦のG1〜G4に加え、エントリー専用のE1/E2まで — 全価格帯を自社シリコンで。"},
    "gpu": {"title": "焔 HOMURA", "en": "GPU", "path": "/tech/gpu/",
            "desc": "自社GPUシリーズ「焔」。レイトレ対応のX系と省電力Lite系、2つのアーキテクチャの進化史。"},
    "memory": {"title": "疾風 HAYATE", "en": "MEMORY", "path": "/tech/memory/",
               "desc": "SoCと同時設計される自社メモリシリーズ「疾風」。エントリーのL1からLPDDR6のM2まで。"},
    "storage": {"title": "瞬 SHUN", "en": "STORAGE", "path": "/tech/storage/",
                "desc": "ロード時間を消しにいく自社ストレージシリーズ「瞬」。エントリーのL1から読込5,800MB/sのS2まで。"},
    "cooling": {"title": "冷却技術", "en": "COOLING", "path": "/tech/cooling/",
                "desc": "氷刃・旋風・液焔・水龍。4つの冷却技術シリーズが、性能の持続を支えます。"},
    "camera": {"title": "天眼 TENGAN", "en": "CAMERA", "path": "/tech/camera/",
               "desc": "自社イメージセンサー「天眼」と神楽ISPによる、SUZAKUのイメージングシステム。"},
}

TYPE_GLOW = {"cpu": "#e8442e", "gpu": "#ff8a3d", "memory": "#3d8bff", "storage": "#38b6a5",
             "cooling": "#4fc3f7", "camera": "#d9a441"}


def tech_bench_charts(t):
    """技術ページ用の世代比較チャート群を生成。"""
    def gen_bar(title, unit, table, fmt=lambda v: v):
        gens = [x for x in TECHS if x["hub"] == t["hub"] and x["id"] in table]
        gens.sort(key=lambda x: x["year"])
        labels = [f"{x['name']}({x['year']})" for x in gens]
        values = [fmt(table[x["id"]]) for x in gens]
        hi = next((i for i, x in enumerate(gens) if x["id"] == t["id"]), None)
        cfg = {"type": "bar", "title": title, "unit": unit, "labels": labels, "values": values}
        if hi is not None:
            cfg["highlight"] = hi
        return chart(cfg)

    out = ""
    if t["id"].startswith("rai-e"):
        hi = 0 if t["id"] == "rai-e1" else 1
        out += chart({"type": "bar", "title": "雷 RAI-Eシリーズ — AnTuTuスコア(参考: 省電力版G4A)", "unit": "万点",
                      "labels": ["RAI-E1(2025)", "RAI-E2(2026)", "参考: RAI-G4A"], "values": [62, 85, 285], "highlight": hi})
        out += chart({"type": "bar", "title": "動画連続再生時間(搭載エントリー機の実測)", "unit": "時間",
                      "labels": ["RAI-E1 搭載機", "RAI-E2 搭載機"], "values": [20, 22], "highlight": hi if hi < 2 else 1})
        return out
    if t["id"].startswith("homura-l"):
        hi = 0 if t["id"] == "homura-l1" else 1
        out += chart({"type": "bar", "title": "焔 Liteシリーズ — 理論演算性能(参考: X2)", "unit": "TFLOPS",
                      "labels": ["HOMURA-L1(2025)", "HOMURA-L2(2026)", "参考: HOMURA-X2"], "values": [0.35, 0.5, 1.6], "highlight": hi})
        return out
    if t["id"] == "hayate-l1":
        out += chart({"type": "bar", "title": "エントリー帯メモリの転送速度比較", "unit": "Mbps",
                      "labels": ["一般的なLPDDR4X", "疾風 HAYATE-L1", "参考: HAYATE-M1"], "values": [4266, 6400, 8533], "highlight": 1})
        return out
    if t["id"] == "shun-l1":
        out += chart({"type": "bar", "title": "エントリー帯ストレージの読込速度比較", "unit": "MB/s",
                      "labels": ["eMMC 5.1", "瞬 SHUN-L1", "参考: SHUN-S1"], "values": [300, 2100, 4300], "highlight": 1})
        return out
    if t["hub"] == "cpu":
        out += gen_bar("雷シリーズ — AnTuTuスコアの世代比較", "万点", ANTUTU)
        out += gen_bar("神楽NPU 推論性能の世代比較", "TOPS", NPU_TOPS)
    elif t["hub"] == "gpu":
        out += gen_bar("焔シリーズ — 理論演算性能の世代比較", "TFLOPS", TFLOPS)
    elif t["hub"] == "memory":
        out += gen_bar("疾風シリーズ — 転送速度の世代比較", "Mbps", MEM_MBPS)
    elif t["hub"] == "storage":
        out += gen_bar("瞬シリーズ — シーケンシャル読込の世代比較", "MB/s", SSD_MBS)
    elif t["id"] == "hyojin":
        out += chart({"type": "bar", "title": "ベイパーチャンバー面積の世代推移", "unit": "mm²",
                      "labels": [k for k, _ in VC_AREA], "values": [v for _, v in VC_AREA], "highlight": 3})
        out += chart({"type": "bar", "title": "表面温度の低下量(当社試験・世代比較)", "unit": "℃",
                      "labels": [k for k, _ in COOL_DELTA], "values": [v for _, v in COOL_DELTA], "highlight": 3})
    elif t["id"] == "senpu":
        out += chart({"type": "bar", "title": "旋風ファン 回転数の世代推移", "unit": "rpm",
                      "labels": [k for k, _ in FAN_RPM], "values": [v for _, v in FAN_RPM], "highlight": 2})
    elif t["id"] == "ekien":
        out += chart({"type": "bar", "title": "サーマル素材の熱伝導率比較", "unit": "W/mK",
                      "labels": ["シリコングリス", "サーマルシート", "液焔(液体金属)"], "values": [4.2, 12, 73], "highlight": 2})
    elif t["id"] == "suiryu":
        out += chart({"type": "bar", "title": "熱輸送量の相対比較(氷刃V4 = 100)", "unit": "",
                      "labels": ["氷刃 V1(2023)", "氷刃 V4(2026)", "水龍(2027予定)"], "values": [52, 100, 320], "highlight": 2})
    elif t["id"] == "tengan-rs2":
        out += chart({"type": "bar", "title": "センサー相対受光面積(RS-1 = 100)", "unit": "",
                      "labels": ["天眼 RS-1(1/1.5型)", "天眼 RS-2(1/1.28型)"], "values": [100, 137], "highlight": 1})
    elif t["id"] == "tengan-rs1":
        out += chart({"type": "bar", "title": "センサー相対受光面積(RS-1 = 100)", "unit": "",
                      "labels": ["天眼 RS-1(1/1.5型)", "天眼 RS-2(1/1.28型)"], "values": [100, 137], "highlight": 0})
    return out


def build_tech_page(t):
    """技術詳細ページ — 左サイド目次(章立て)+ 右本文のドキュメント型レイアウト。"""
    hub = TECH_HUBS[t["hub"]]
    glow = TYPE_GLOW[t["type"]]
    url = f"/tech/{t['hub']}/{t['id']}/"
    hero_art = svg_art.svg_die(t["id"], t["en"], f"SUZAKU {t['type'].upper()} / {t['year']}", glow) \
        if t["type"] in ("cpu", "gpu", "memory", "storage") else svg_art.svg_art(
            {"cooling": "cooling", "camera": "camera"}.get(t["type"], "chip"), glow)
    if t["id"] == "senpu":
        hero_art = svg_art.svg_art("fan", glow)
    if t["id"] in ("ekien", "suiryu"):
        hero_art = svg_art.svg_art("liquid", glow)

    bench = tech_bench_charts(t)

    # 目次
    toc = ['<a href="#overview">概要と主要数値</a>']
    if bench:
        toc.append('<a href="#bench">ベンチマーク・世代比較</a>')
    sec_html = []
    for i, sec in enumerate(t["sections"]):
        title_plain = re.sub(r"<[^>]+>", "", sec["title"])
        toc.append(f'<a href="#sec-{i}">{esc(title_plain)}</a>')
        rev = " feature-split--rev" if i % 2 else ""
        pts = "".join(f"<li>{p}</li>" for p in sec.get("points", []))
        link = f'<a class="link-arrow" href="{sec["link"][0]}">{sec["link"][1]}</a>' if sec.get("link") else ""
        sec_html.append(f"""
<div class="feature-split{rev}" id="sec-{i}" style="scroll-margin-top:90px">
  <div class="feature-split__media reveal-scale">{svg_art.svg_art(sec.get('art', 'chip'), glow)}</div>
  <div class="stack reveal">
    <p class="eyebrow">{sec['eyebrow']}</p>
    <h2 class="t-h3">{sec['title']}</h2>
    <p class="t-soft t-small">{sec['body']}</p>
    <ul class="check-list">{pts}</ul>
    {link}
  </div>
</div>""")
    toc.append('<a href="#spec">仕様</a>')

    prods = [x for x in ALL_PRODUCTS if x["id"] in t.get("products", [])]
    prods_html = ""
    if prods:
        toc.append('<a href="#products">搭載製品</a>')
        prods_html = f"""
<div id="products" style="scroll-margin-top:90px">
  <h2 class="t-h3" style="margin-bottom:18px">{esc(t['name'])} 搭載製品</h2>
  <div class="grid grid--3 grid--cards reveal-stagger">{''.join(product_card(x) for x in prods[:3])}</div>
</div>"""

    siblings = sorted([x for x in TECHS if x["hub"] == t["hub"] and x["id"] != t["id"]], key=lambda x: -x["year"])
    sib_side = "".join(
        f'<a href="/tech/{x["hub"]}/{x["id"]}/">{esc(x["name"])}<small style="color:var(--text-faint)">({x["year"]})</small></a>'
        for x in siblings)

    body = f"""
<section class="hero hero--page">
  <div class="hero__inner hero-enter">
    <p class="eyebrow">{hub['en']} — {t['announce']} 発表</p>
    <h1 class="t-display">{esc(t['name'])}</h1>
    <p class="t-lead" style="max-width:680px">{esc(t['tagline'])}</p>
    <p class="t-soft t-small" style="max-width:680px">{esc(t['sub'])}</p>
  </div>
</section>
<section class="section--sm section--flush-top" style="padding-top:var(--sp-5)">
  <div class="container">
    <div class="doc-layout">
      <aside class="doc-side">
        <p class="doc-side__title">このページの内容</p>
        {''.join(toc)}
        <p class="doc-side__title">{hub['title']} の他の世代</p>
        {sib_side}
        <p class="doc-side__title">シリーズ</p>
        <a href="{hub['path']}">{hub['title']} トップ</a>
        <a href="/tech/">テクノロジー トップ</a>
      </aside>
      <div class="stack" style="gap:var(--sp-8)">
        <div id="overview" style="scroll-margin-top:90px" class="stack stack--lg">
          <div class="chip-visual reveal-scale" style="max-width:520px">{hero_art}</div>
          {stats_html(t['stats'])}
        </div>
        {f'<div id="bench" style="scroll-margin-top:90px" class="chart-grid">{bench}</div>' if bench else ''}
        {''.join(sec_html)}
        <div id="spec" style="scroll-margin-top:90px" class="reveal">{spec_tables_html(t['specs'])}</div>
        {prods_html}
      </div>
    </div>
  </div>
</section>
{related_news_section([t['name'], t['en']], title=f"{esc(t['name'])} 関連ニュース")}
{cta_minimal('技術は、体験のためにある。', [('搭載製品をストアで見る', '/store/'), (hub['title'] + ' トップ', hub['path']), ('テクノロジー トップ', '/tech/')])}
"""
    crumbs = [("テクノロジー", "/tech/"), (hub["title"], hub["path"]), (t["name"], None)]
    render_page(url, f"{t['name']} — {t['tagline']}", t["sub"], body, "dark", crumbs, "テクノロジー")


HUB_TRENDS = {
    "cpu": [("AnTuTuスコアの推移", "万点", ANTUTU), ("最大クロックの推移", "GHz", CLOCK), ("神楽NPU 推論性能の推移", "TOPS", NPU_TOPS)],
    "gpu": [("理論演算性能の推移", "TFLOPS", TFLOPS)],
    "memory": [("転送速度の推移", "Mbps", MEM_MBPS)],
    "storage": [("シーケンシャル読込の推移", "MB/s", SSD_MBS)],
}


def build_tech_hub(hub_key):
    """技術ハブ — 世代タイムライン横スクロール + トレンドグラフ。"""
    hub = TECH_HUBS[hub_key]
    glow = TYPE_GLOW[hub_key]
    gens = sorted([t for t in TECHS if t["hub"] == hub_key], key=lambda x: x["year"])

    # 世代タイムライン(古い→新しい、横スクロール)
    rail_cards = "".join(f"""
<a class="card card--hover" href="/tech/{hub_key}/{t['id']}/">
  <p class="gen-rail__year">{t['year']}</p>
  <h2 class="t-h3">{esc(t['name'])}</h2>
  <p class="t-soft t-small">{esc(t['tagline'])}</p>
  <p class="t-micro t-faint">{esc(t['sub'][:64])}…</p>
  <p class="link-arrow">技術詳細を見る</p>
</a>""" for t in gens)

    # トレンド折れ線グラフ
    trend_charts = ""
    for title, unit, table in HUB_TRENDS.get(hub_key, []):
        pts = [(t["year"], table[t["id"]]) for t in gens if t["id"] in table]
        if len(pts) >= 2:
            trend_charts += chart({"type": "line", "title": f"{hub['title']} — {title}", "unit": unit, "area": True,
                                   "labels": [f"{y}年" for y, _ in pts], "series": [{"name": hub["title"], "values": [v for _, v in pts]}]})
    if hub_key == "cpu":
        trend_charts += chart({"type": "bar", "title": "エントリー向け 雷 RAI-Eシリーズ(参考: 省電力版G4A)", "unit": "万点",
                               "labels": ["RAI-E1(2025)", "RAI-E2(2026)", "参考: RAI-G4A"], "values": [62, 85, 285], "highlight": 1})
    if hub_key == "gpu":
        trend_charts += chart({"type": "bar", "title": "省電力Liteシリーズ 焔 HOMURA-L", "unit": "TFLOPS",
                               "labels": ["HOMURA-L1(2025)", "HOMURA-L2(2026)", "参考: HOMURA-X2"], "values": [0.35, 0.5, 1.6], "highlight": 1})
    if hub_key == "memory":
        trend_charts += chart({"type": "bar", "title": "エントリー向け 疾風 HAYATE-L1", "unit": "Mbps",
                               "labels": ["一般的なLPDDR4X", "HAYATE-L1", "HAYATE-M2"], "values": [4266, 6400, 10667], "highlight": 1})
    if hub_key == "storage":
        trend_charts += chart({"type": "bar", "title": "エントリー向け 瞬 SHUN-L1", "unit": "MB/s",
                               "labels": ["eMMC 5.1", "SHUN-L1", "SHUN-S2"], "values": [300, 2100, 5800], "highlight": 1})
    if hub_key == "cooling":
        trend_charts += chart({"type": "line", "title": "氷刃 ベイパーチャンバー面積の推移", "unit": "mm²", "area": True,
                               "labels": ["2023年", "2024年", "2025年", "2026年"],
                               "series": [{"name": "氷刃", "values": [v for _, v in VC_AREA]}]})
        trend_charts += chart({"type": "bar", "title": "表面温度の低下量(当社試験)", "unit": "℃",
                               "labels": [k for k, _ in COOL_DELTA], "values": [v for _, v in COOL_DELTA], "highlight": 3})
    if hub_key == "camera":
        trend_charts += chart({"type": "bar", "title": "センサー相対受光面積(RS-1 = 100)", "unit": "",
                               "labels": ["天眼 RS-1(2024)", "天眼 RS-2(2025)"], "values": [100, 137], "highlight": 1})
        trend_charts += chart({"type": "bar", "title": "神楽ISP 画像処理能力の推移", "unit": "億画素/秒",
                               "labels": ["2024(RS-1世代)", "2025(RS-2世代)", "2026(RS-2+世代)"], "values": [14, 24, 32], "highlight": 2})

    # カメラハブ専用: イメージングパイプラインの解説(センサー→ISP→演算処理の全体像)
    hub_extra = ""
    if hub_key == "camera":
        hub_extra = f"""
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">IMAGING PIPELINE</p><h2 class="t-h2">シャッターの裏側、0.1秒の分業。</h2>
    <p class="t-soft">天眼はセンサー単体の名前ではありません。受光・処理・演算がひとつの設計で貫かれた、イメージングシステムの総称です。</p></div>
    <div class="grid grid--3 grid--cards reveal-stagger">
      <div class="card"><p class="eyebrow">1. SENSOR</p><h3 class="t-h4">天眼センサーが受け止める</h3><p class="t-small t-soft">1/1.28型の大型センサーとデュアルネイティブISOで、夜のネオンも昼の逆光もRAWのまま取り込みます。</p></div>
      <div class="card"><p class="eyebrow">2. ISP</p><h3 class="t-h4">神楽ISPがさばく</h3><p class="t-small t-soft">SoC統合ISPが毎秒32億画素を3系統同時処理。8K動画を撮りながら静止画を切り出せるのはこの帯域のおかげです。</p></div>
      <div class="card"><p class="eyebrow">3. AI</p><h3 class="t-h4">神楽NPUが仕上げる</h3><p class="t-small t-soft">120TOPSのNPUがノイズ除去・HDR合成・被写体認識をリアルタイム実行。<a href="/tech/ai/">神楽 AIエンジン</a>と同じ頭脳です。</p></div>
    </div>
    <div class="notice reveal" style="margin-top:24px"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5h.01"/></svg> ゲーミングフォンにカメラは不要? — 私たちはそう思いません。攻略の記録、戦績のシェア、日常の一枚。ゲームと同じ本気で、カメラを作っています。搭載機は<a href="/products/phone/suzaku-4/">SUZAKU 4</a>・<a href="/products/phone/tsubame-3/">TSUBAME 3</a>をご覧ください。</div>
  </div>
</section>"""

    trend_html = f"""
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">TREND</p><h2 class="t-h2">数字で見る進化</h2></div>
    <div class="chart-grid">{trend_charts}</div>
  </div>
</section>""" if trend_charts else ""

    body = f"""
<section class="hero hero--sub">
  <div class="hero__bg hero__bg--glow" style="background:radial-gradient(50% 40% at 50% 70%, {glow}3d, transparent 70%), var(--bg-deep)"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">{hub['en']}</p>
    <h1 class="t-hero">{hub['title']}</h1>
    <p class="t-lead" style="max-width:660px">{hub['desc']}</p>
  </div>
</section>
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">GENERATIONS</p><h2 class="t-h2">世代タイムライン</h2>
    <p class="t-soft t-small">横にスクロールして、{gens[0]['year']}年から{gens[-1]['year']}年までの進化をたどれます。</p></div>
    <div class="gen-rail">{rail_cards}</div>
  </div>
</section>
{trend_html}
{hub_extra}
{cta_band('すべての技術は、つながっている。', 'SoC・メモリ・冷却・OSの垂直統合こそ、SUZAKUの体験の正体です。', [('テクノロジー トップ', '/tech/', 'btn--primary'), ('製品を見る', '/products/', 'btn--ghost')])}
"""
    render_page(hub["path"], f"{hub['title']}({hub['en']})", hub["desc"], body, "dark",
                [("テクノロジー", "/tech/"), (hub["title"], None)], "テクノロジー")


# ==========================================================================
# OSページ
# ==========================================================================

def build_os_pages():
    latest = OS_VERSIONS[0]
    # ハブ
    ver_cards = "".join(f"""
<a class="card card--hover reveal" href="/os/{v['path']}/">
  <p class="eyebrow">{v['announce']} / {v['base']}ベース</p>
  <h2 class="t-h3">{esc(v['name'])} <span class="grad-text">「{v['code']}」</span></h2>
  <p class="t-soft t-small">{esc(v['sub'])}</p>
  <p class="link-arrow">詳細を見る</p>
</a>""" for v in OS_VERSIONS)
    body = f"""
<section class="hero">
  <canvas class="hero__canvas" id="emberCanvas" aria-hidden="true"></canvas>
  <div class="hero__bg hero__bg--glow"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">SUZAKU OS</p>
    <h1 class="t-hero">ゲームのために<br>生まれた<span class="grad-text">OS</span>。</h1>
    <p class="t-lead" style="max-width:640px">タッチの一瞬を最優先するスケジューラ、冷却と性能の自動最適化、そしてゲームスペース「陣」。SUZAKU OSは、ハードウェアと同じ設計思想で書かれています。</p>
    <div class="hero__actions">
      <a class="btn btn--primary btn--lg" href="/os/v4/">最新 {esc(latest['name'])}「{latest['code']}」</a>
      <a class="btn btn--ghost btn--lg" href="/os/game-space/">ゲームスペース「陣」</a>
    </div>
  </div>
  <div class="hero__scroll-cue" aria-hidden="true"></div>
</section>
<section class="section">
  <div class="container">
    <div class="section-head"><p class="eyebrow">VERSIONS</p><h2 class="t-h2">SUZAKU OS、4つの章。</h2>
    <p class="t-soft">2023年の1.0「暁」から、毎年ひとつの章を重ねてきました。全バージョンの記録です。</p></div>
    <div class="grid grid--2">{ver_cards}</div>
  </div>
</section>
{cta_band('OSも、アップデートも、無償で。', 'SUZAKU OSは全対応端末に無償提供。フラッグシップは3世代、TSUBAMEは4世代のアップデートを保証します。', [('対応製品を見る', '/products/', 'btn--primary'), ('アップデート情報', '/support/downloads/', 'btn--ghost')])}
"""
    render_page("/os/", "SUZAKU OS — ゲームのために生まれたOS",
                "独自OS「SUZAKU OS」の全バージョンとゲームスペース「陣」。タッチ最優先スケジューラと冷却×性能の自動最適化。",
                body, "dark", [("SUZAKU OS", None)], "OS")

    # 各バージョン
    for i, v in enumerate(OS_VERSIONS):
        feats = "".join(f"""
<div class="card reveal"><div class="card__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l2.5 5.5L20 10l-5.5 1.5L12 17l-2.5-5.5L4 10l5.5-1.5z"/></svg></div>
<h3 class="t-h4">{esc(f['t'])}</h3><p class="t-small t-soft">{esc(f['d'])}</p></div>""" for f in v["features"])
        others = "".join(
            f'<a class="tab{" is-active" if o["id"] == v["id"] else ""}" href="/os/{o["path"]}/">{o["name"].replace("SUZAKU OS ", "")}「{o["code"]}」</a>'
            for o in reversed(OS_VERSIONS))
        body = f"""
<section class="hero hero--sub">
  <div class="hero__bg hero__bg--glow"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">{v['announce']} / {v['base']}ベース</p>
    <h1 class="t-display">{esc(v['name'])}<br><span class="grad-text">「{v['code']} — {v['en']}」</span></h1>
    <p class="t-lead" style="max-width:640px">{esc(v['tagline'])}<br><span class="t-small">{esc(v['sub'])}</span></p>
  </div>
</section>
<section class="section--sm"><div class="container"><div class="tabs" style="justify-content:center">{others}</div></div></section>
<section class="section--sm"><div class="container">{stats_html(v['stats'])}</div></section>
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">FEATURES</p><h2 class="t-h2">{esc(v['name'])} の主な機能</h2></div>
    <div class="grid grid--3">{feats}</div>
  </div>
</section>
{svg_os_showcase(v)}
<section class="section--sm">
  <div class="container container--narrow">
    <div class="section-head"><p class="eyebrow">RELEASE NOTES</p><h2 class="t-h2">配信履歴</h2></div>
    <div class="scroll-x reveal"><table class="spec-table">
      <thead><tr><th scope="col" style="padding:12px 18px;text-align:left">バージョン</th><th scope="col" style="padding:12px 18px;text-align:left">配信日</th><th scope="col" style="padding:12px 18px;text-align:left">主な内容</th></tr></thead>
      <tbody>{''.join(f'<tr><th scope="row">{ver}</th><td style="white-space:nowrap">{date}</td><td>{note}</td></tr>' for ver, date, note in v.get('patches', []))}</tbody>
    </table></div>
    <p class="t-micro t-faint" style="margin-top:14px">機種ごとの配信状況は<a href="/support/downloads/" style="color:var(--accent);text-decoration:underline">ダウンロード</a>ページをご確認ください。</p>
  </div>
</section>
{cta_band('「陣」で、すべてのゲームをひとつに。', 'SUZAKU OSの中核、ゲームスペース「陣」の全機能をご覧ください。', [('ゲームスペース「陣」', '/os/game-space/', 'btn--primary'), ('OS トップへ', '/os/', 'btn--ghost')])}
"""
        render_page(f"/os/{v['path']}/", f"{v['name']}「{v['code']}」",
                    v["sub"], body, "dark", [("SUZAKU OS", "/os/"), (f"{v['name']}「{v['code']}」", None)], "OS")


def svg_os_showcase(v):
    art = svg_art.svg_art("os", "#e8442e")
    return f"""
<section class="section--sm">
  <div class="container">
    <div class="feature-split">
      <div class="feature-split__media reveal-scale">{art}</div>
      <div class="stack reveal">
        <p class="eyebrow">DESIGN</p>
        <h2 class="t-h2">「{v['code']}」のデザイン言語。</h2>
        <p class="t-soft">SUZAKU OSの各バージョンには日本語の開発コードが与えられ、その名を冠したテーマ・サウンド・ライブ壁紙が同梱されます。{esc(v['name'])}「{v['code']}」も、朱と黒を基調にした独自のビジュアルシステムを備えています。</p>
        <ul class="check-list"><li>ダイナミックカラーテーマ「{v['code']}」</li><li>144Hz駆動のシステムアニメーション</li><li>プリインストール広告ゼロ</li></ul>
      </div>
    </div>
  </div>
</section>"""


# ==========================================================================
# ニュース
# ==========================================================================

def build_news_pages():
    for i, n in enumerate(NEWS):
        paras = "".join(f"<p>{p}</p>" for p in n["body"])
        prev_link = f'<a class="btn btn--ghost btn--sm" href="/news/{NEWS[i + 1]["id"]}/">← 前の記事</a>' if i + 1 < len(NEWS) else ""
        next_link = f'<a class="btn btn--ghost btn--sm" href="/news/{NEWS[i - 1]["id"]}/">次の記事 →</a>' if i > 0 else ""
        body = f"""
<section class="hero hero--page">
  <div class="hero__inner hero-enter">
    <p class="eyebrow">ニュースルーム — {n['cat']}</p>
    <h1 class="t-h1" style="max-width:840px">{esc(n['title'])}</h1>
    <p class="t-soft t-small">{n['date'].replace('-', '.')} — 株式会社朱雀</p>
  </div>
</section>
<article class="section--sm">
  <div class="container container--text">
    <div class="prose reveal">{paras}</div>
    <hr class="divider" style="margin-block:40px">
    <div class="prose t-small t-soft">
      <p><strong>株式会社朱雀(SUZAKU Inc.)について</strong><br>
      2022年5月1日設立。「限界を、燃やし尽くせ。」をタグラインに、ゲーミングスマートフォン・タブレットとその中核半導体(SoC・GPU・メモリ・ストレージ)、冷却技術、独自OSを自社開発する日本のハードウェアメーカーです。本社: 東京都千代田区外神田。</p>
      <p>本件に関する報道関係者からのお問い合わせ: <a href="/support/contact/">お問い合わせフォーム</a>(広報宛)</p>
    </div>
    <div class="spread" style="margin-top:36px">{prev_link}<a class="btn btn--soft btn--sm" href="/news/">ニュース一覧</a>{next_link}</div>
  </div>
</article>
"""
        render_page(f"/news/{n['id']}/", n["title"], n["excerpt"], body, "light",
                    [("ニュースルーム", "/news/"), (n["date"][:4] + "年", None)], "ニュース")


# ==========================================================================
# コラボレーション特設 — 作品ごとに完全個別設計のLP
# 共有するのは購入モジュール(カウントダウン/在庫/CTA)と注記のみ(collab-core)。
# 骨格・背景・フォント・演出は _collab_lp_{slug}() + collab-{slug}.css/js が持つ。
# ==========================================================================

# コラボLP限定の追加フォント(非ブロッキング読み込み)
COLLAB_FONTS = {
    "genshin": """<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;700;800&display=swap" media="print" onload="this.media='all'">""",
    "wuwa": """<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;700;900&display=swap" media="print" onload="this.media='all'">""",
    "nte": """<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:ital,wght@0,700;1,800;1,900&display=swap" media="print" onload="this.media='all'">""",
    "endfield": """<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&display=swap" media="print" onload="this.media='all'">""",
}


def _cl_lpnav(cfg, phone):
    """LP専用ミニヘッダー(進行バー付き)。通常ナビとは別物。
    phone があるLP本体では #buy へ、無いページ(シリコン等)ではLPへ誘導する。"""
    price = f'<span class="cl-lpnav__price">{yen(phone["price"])}〜</span>' if phone else ""
    cta = ('<a class="cl-lpnav__buy" href="#buy">購入へ</a>' if phone
           else f'<a class="cl-lpnav__buy" href="/collab/{cfg["slug"]}/">特設へ</a>')
    return f"""
<div class="cl-lpnav" id="clLpnav">
  <div class="cl-lpnav__in">
    <a class="cl-lpnav__back" href="/collab/">← COLLAB</a>
    <span class="cl-lpnav__name">{esc(cfg['edition'])}</span>
    {price}{cta}
  </div>
  <span class="cl-lpnav__bar" aria-hidden="true"></span>
</div>"""


def _cl_commerce(cfg, phone):
    """共通購入モジュール: カウントダウン+在庫メーター+CTA(collab-core.css)。"""
    lim = cfg["limited"]
    slug = cfg["slug"]
    buy = ""
    price_html = ""
    if phone:
        buy = (f'<a class="cl-btn cl-btn--primary" href="{product_url(phone)}">製品詳細・購入へ</a>'
               f'<a class="cl-btn cl-btn--ghost" href="/products/compare/">通常モデルと比較</a>')
        price_html = f'<span class="cl-buy__price">{yen(phone["price"])}<small>(税込)〜</small></span>'
    return f"""
<section class="cl-section cl-limited" id="buy">
  <div class="cl-wrap cl-limited__grid">
    <div class="cl-count" data-until="{lim['until']}" role="timer" aria-label="受付終了までの残り時間">
      <p class="cl-eyebrow">受付終了まで</p>
      <div class="cl-count__row">
        <span class="cl-count__unit"><b data-c="d">--</b><i>日</i></span>
        <span class="cl-count__unit"><b data-c="h">--</b><i>時間</i></span>
        <span class="cl-count__unit"><b data-c="m">--</b><i>分</i></span>
        <span class="cl-count__unit"><b data-c="s">--</b><i>秒</i></span>
      </div>
      <p class="cl-count__end">{esc(lim['until'][:10])} まで</p>
    </div>
    <div class="cl-stock" data-slug="{slug}" data-qty="{lim['qty']}" data-sold="{lim['sold']}">
      <p class="cl-eyebrow">数量限定 生産数</p>
      <div class="cl-stock__bar"><span class="cl-stock__fill"></span></div>
      <p class="cl-stock__meta"><b class="cl-stock__remain">--</b> / {lim['qty']:,} 台 が販売可能</p>
    </div>
  </div>
  <div class="cl-wrap cl-buy__inner">
    {f'''<div class="cl-buy__media" data-clview-scope>
      <img class="clview-img" src="{pimg(phone['id'])}" data-back-src="{pimg(phone['id'])}" data-front-src="{pimg_front(phone['id'])}" alt="{esc(phone['name'])}" width="180" height="318" loading="lazy">
      <div class="cl-view" role="group" aria-label="表示切替">
        <button type="button" class="cl-view__btn is-on" data-clview="back" aria-pressed="true">背面</button>
        <button type="button" class="cl-view__btn" data-clview="front" aria-pressed="false">正面</button>
      </div>
    </div>''' if phone else ''}
    <div>
      <p class="cl-eyebrow">数量限定・期間限定</p>
      <h2 class="cl-h2">{esc(cfg['edition'])}</h2>
      {price_html}
    </div>
    <div class="cl-buy__cta">{buy}</div>
  </div>
</section>"""


def _cl_schedule(cfg):
    items = "".join(
        f'<li class="cl-sched__i reveal"><span class="cl-sched__d">{esc(d)}</span>'
        f'<strong class="cl-sched__t">{esc(t)}</strong><span class="cl-sched__b">{esc(b)}</span></li>'
        for d, t, b in cfg.get("schedule", []))
    if not items:
        return ""
    return f"""
<section class="cl-section">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">SCHEDULE</p><h2 class="cl-h2">スケジュール</h2></div>
    <ol class="cl-sched">{items}</ol>
  </div>
</section>"""


def _cl_faq(cfg):
    items = "".join(
        f'<details class="cl-faq__i"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>'
        for q, a in cfg.get("faq", []))
    if not items:
        return ""
    return f"""
<section class="cl-section">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">FAQ</p><h2 class="cl-h2">よくある質問</h2></div>
    <div class="cl-faq">{items}</div>
  </div>
</section>"""


def _cl_accs(cfg, accs):
    if not accs:
        return ""
    cards = "".join(
        f'<a class="cl-acc" href="{product_url(a)}">'
        f'<div class="cl-acc__media"><img src="{pimg(a["id"])}" alt="{esc(a["name"])}" loading="lazy" width="240" height="240"></div>'
        f'<div class="cl-acc__body"><p class="cl-acc__name">{esc(a["name"])}</p>'
        f'<p class="cl-acc__copy">{esc(a["tagline"])}</p>'
        f'<p class="cl-acc__price">{yen(a["price"])} <small>(税込)〜</small></p></div></a>'
        for a in accs)
    return f"""
<section class="cl-section">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">COLLAB ACCESSORY</p><h2 class="cl-h2">専用アクセサリ</h2></div>
    <div class="cl-accs">{cards}</div>
  </div>
</section>"""


def _cl_bundle(cfg):
    items = "".join(
        f'<li class="cl-bundle__i"><strong>{esc(b["title"])}</strong><span>{esc(b["desc"])}</span></li>'
        for b in cfg.get("bundle", []))
    return f"""
<section class="cl-section">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">IN THE BOX</p><h2 class="cl-h2">同梱バンドル</h2></div>
    <ul class="cl-bundle__list">{items}</ul>
  </div>
</section>"""


def _cl_silicon(cfg):
    slug = cfg["slug"]
    comps = COLLAB_SILICON.get(slug, [])
    cards = "".join(
        f'<a class="cl-si-card" href="{collab_silicon_url(slug, c["key"])}">'
        f'<span class="cl-si-card__comp">{esc(c["comp"])} — 専用設計</span>'
        f'<span class="cl-si-card__brand">{esc(c["name"])}</span>'
        f'<span class="cl-si-card__kick">{esc(c["kicker"])}</span></a>'
        for c in comps)
    if not cards:
        return ""
    return f"""
<section class="cl-section">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">DEDICATED SILICON</p><h2 class="cl-h2">専用設計シリコン。</h2>
    <p class="cl-lead">{esc(cfg['device'])}のためだけに新規設計した、SoC・GPU・メモリ・ストレージ。既存チップの選別や流用は、一切ありません。</p></div>
    <div class="cl-si-cards">{cards}</div>
    <div style="margin-top:16px"><a class="cl-btn cl-btn--ghost" href="/collab/silicon/">すべての専用シリコンを見る</a></div>
  </div>
</section>"""


def _cl_note(cfg):
    return (f'<p class="cl-note">{esc(cfg["note"])} 本サイトは架空企業「株式会社朱雀」のデモンストレーションであり、'
            f'実在の商品・価格・提携・販売を示すものではありません。</p>'
            f'<div class="cl-backlink"><a href="/collab/">← すべてのコラボレーションを見る</a></div>')


def _cl_stats(phone):
    if not phone:
        return ""
    return "".join(
        f'<div class="cl-stat reveal"><span class="cl-stat__v">{esc(str(s["v"]))}<i>{esc(s["u"])}</i></span>'
        f'<span class="cl-stat__l">{esc(s["l"])}</span></div>'
        for s in phone.get("stats", []))


def _collab_lp_genshin(cfg, phone, accs):
    """原神「七耀」LP — 白×金の明色ファンタジー・明朝・元素ホイール・雲パララックス。"""
    elems = [("風", "#4dd6c1"), ("岩", "#e5b53a"), ("雷", "#b18bff"), ("草", "#8bd450"),
             ("水", "#3fb6ff"), ("炎", "#ff6a4d"), ("氷", "#7fe8ff")]
    chips = "".join(
        f'<button type="button" class="gs-elem" data-elem="{e}" style="--el:{c}"><span>{e}</span></button>'
        for e, c in elems)
    intro_dots = "".join(f'<span class="gs-intro__dot" style="--el:{c};--i:{i}"></span>' for i, (e, c) in enumerate(elems))
    terms = [
        ("旅人", "テイワットを旅する主人公。七耀は、その旅路のための一台です。"),
        ("七元素", "風・岩・雷・草・水・炎・氷。世界を構成する七つの力。背面の元素リングが、その色で灯ります。"),
        ("七天神像", "旅の道標。原神コラボ・モバイルバッテリーの意匠にもあしらいました。"),
    ]
    term_cards = "".join(
        f'<div class="gs-term reveal"><h3>{esc(t)}</h3><p>{esc(b)}</p></div>' for t, b in terms)

    # --- 追補: 七元素チューニング表(元素ごとの表示・触覚・リング発光の作り込み) ---
    tunings = [
        ("風", "#4dd6c1", "翡翠の残光", "そよぐ長い余韻の微振動", "円環が時計回りに流れる"),
        ("岩", "#e5b53a", "琥珀の重心", "短く硬い、岩を打つ手応え", "全周が一拍で点灯し沈む"),
        ("雷", "#b18bff", "紫電の走査", "鋭い二連の刺激", "対角2点が交互に瞬く"),
        ("草", "#8bd450", "若葉の階調", "柔らかい波状の連なり", "下から上へ芽吹くように点る"),
        ("水", "#3fb6ff", "深浅の青緻", "揺れて減衰する波紋", "波紋状に外周へ広がる"),
        ("炎", "#ff6a4d", "緋色の高輝", "立ち上がりの速い熱い一撃", "鼓動のように強弱を刻む"),
        ("氷", "#7fe8ff", "霜白の冷艶", "細かく凍てつく粒の連打", "結晶状に6点が同時に灯る"),
    ]
    tune_rows = "".join(
        f'<div class="gs-tune reveal" style="--el:{c}"><span class="gs-tune__el">{e}</span>'
        f'<span class="gs-tune__tone"><small>表示チューニング</small>{esc(tone)}</span>'
        f'<span class="gs-tune__hap"><small>共鳴ハプティクス</small>{esc(hap)}</span>'
        f'<span class="gs-tune__ring"><small>元素リング発光</small>{esc(ring)}</span></div>'
        for e, c, tone, hap, ring in tunings)

    # --- 追補: 開発紀行(共同開発の長文3章) ---
    journeys = [
        ("壱", "白磁を、焼き物から学ぶ", "七耀の白は、ディスプレイの白ではなく、器の白です。共同チームは企画初期に磁器工房を訪ね、釉薬の「沈む白」を分光計で採取しました。ガラス蒸着を42回試作し、光を反射するのではなく一度含んでから返す白磁調の積層に到達。テイワットの陶都の空気を、背面ガラス0.7mmの中に封じています。"),
        ("弐", "空の色を、実測する", "原神の空は時間で色を変えます。開発チームはゲーム内の朝・昼・黄昏・夜の空を計1,200フレームぶん色度計で実測し、元素燐光ディスプレイの色管理テーブルへ翻訳しました。BT.2020 110%という数字は、あの黄昏の茜色を諦めないための下限値です。"),
        ("参", "金彩は、線の細さで決まる", "フレームの金彩は、太いと武具になり、細いと消えます。0.4mmから1.6mmまで9段階の飾り線を削り出し、手に持ったときに視界の端で「ほのかに光る」1.1mmを採用しました。178回目の蒸着試作に、チームは「これは道具ではなく、旅の記念品だ」と記しています。"),
    ]
    journey_blocks = "".join(
        f'<article class="gs-journey__ch reveal"><span class="gs-journey__no">{no}</span>'
        f'<h3>{esc(t)}</h3><p>{esc(b)}</p></article>'
        for no, t, b in journeys)

    # --- 追補: 実測レポート(原神プレイの当社試験値) ---
    fps_cols = "".join(
        f'<div class="gs-fpscol"><i style="--h:{h}%"></i><span>{m}</span></div>'
        for m, h in [("0分", 100), ("10分", 100), ("20分", 99), ("30分", 99), ("45分", 99), ("60分", 98)])
    lab_stats = [
        ("60", "fps", "最高画質・60fps設定で張り付き(当社試験値)"),
        ("99.2", "%", "60分連続プレイのフレーム安定率"),
        ("11.4", "時間", "フィールド探索の連続駆動(7,900mAh)"),
        ("42.8", "℃", "60分後の背面最高温度"),
    ]
    lab_cells = "".join(
        f'<div class="gs-lab__cell reveal"><b>{v}</b><i>{u}</i><span>{esc(d)}</span></div>'
        for v, u, d in lab_stats)

    # --- 追補: 限定テーマパック詳細 ---
    theme_items = [
        ("ロック画面「七耀の空」", "時間帯で空の色が移ろい、選択中の元素の粒子が舞う"),
        ("アイコンセット「金彩」", "白磁地に金の細線で描き直した約120種"),
        ("通知音「七元素の音階」", "元素ごとに音色が変わる7音のチャイム"),
        ("起動音とリング連動", "起動時に背面リングが七色を一巡して点灯"),
        ("AOD「元素時計」", "常時表示に元素ホイールの時計盤"),
        ("限定壁紙 14枚", "七元素×昼夜の描き下ろし(デモ表記)"),
    ]
    theme_rows = "".join(
        f'<li class="gs-theme__i reveal"><b>{esc(t)}</b><span>{esc(d)}</span></li>'
        for t, d in theme_items)

    # --- 追補: コレクターズボックス展開 ---
    box_items = [
        ("一", "七耀 本体", "白磁または金彩"),
        ("二", "七天神像モバイルバッテリー引換券", "同梱バンドルの案内状"),
        ("三", "白磁ケース", "薄型1.2mm・金彩リム"),
        ("四", "金彩カード「旅の許可証」", "シリアル番号入り(8,000分の1)"),
        ("五", "元素リング・クロス", "白磁の艶を保つ専用クロス"),
        ("六", "100W 充電アダプタ", "白磁調の限定色"),
        ("七", "テーマパック引換コード", "七耀の空・金彩アイコン他"),
    ]
    box_rows = "".join(
        f'<div class="gs-box__i reveal"><span class="gs-box__no">{no}</span><b>{esc(t)}</b><span class="gs-box__d">{esc(d)}</span></div>'
        for no, t, d in box_items)

    gs_ext = f"""
<section class="cl-section gs-tuning">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">ELEMENTAL TUNING</p><h2 class="cl-h2">七元素、七通りの作り込み。</h2>
    <p class="cl-lead">元素テーマは色替えではありません。表示の色調・共鳴ハプティクスの波形・背面リングの点灯パターンまで、七元素それぞれに専用チューニングを施しました。</p></div>
    <div class="gs-tunes">{tune_rows}</div>
    <p class="gs-tuning__note">テーマ切替は 設定 → テーマ → 七耀 から。元素はホーム画面の長押しでも変更できます。</p>
  </div>
</section>

<section class="cl-section gs-journey">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">DEVELOPMENT NOTES</p><h2 class="cl-h2">開発紀行 — 白磁と金彩の記録。</h2>
    <p class="cl-lead">SUZAKUとHoYoverseの共同設計チームが残した、七耀ができるまでの三つの章。</p></div>
    <div class="gs-journey__grid">{journey_blocks}</div>
  </div>
</section>

<section class="cl-section gs-lab">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">FIELD REPORT</p><h2 class="cl-h2">実測レポート — 原神を、七耀で。</h2>
    <p class="cl-lead">最高画質・60fps設定での当社試験値。数字は誇張ではなく、旅の実感のために。</p></div>
    <div class="gs-lab__grid">{lab_cells}</div>
    <div class="gs-fps reveal">
      <p class="gs-fps__cap">60分連続プレイのfps推移(最高画質・60fps設定・当社試験値)</p>
      <div class="gs-fps__cols">{fps_cols}</div>
    </div>
  </div>
</section>

<section class="cl-section gs-themepack">
  <div class="cl-wrap gs-split">
    <div class="gs-split__media reveal"><img src="{pimg_front(phone['id'])}" alt="七耀 限定テーマの正面表示" width="250" height="441" loading="lazy"></div>
    <div class="gs-split__copy reveal">
      <p class="cl-eyebrow">THEME PACK</p>
      <h2 class="cl-h2">限定テーマパック、全6点。</h2>
      <p>画面の中まで、七耀です。ロック画面・アイコン・通知音・AODを白磁と金彩の意匠で描き直しました。</p>
      <ul class="gs-theme__list">{theme_rows}</ul>
    </div>
  </div>
</section>

<section class="cl-section gs-boxsec">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">COLLECTOR'S BOX</p><h2 class="cl-h2">コレクターズボックス、七つの同梱。</h2>
    <p class="cl-lead">飾って残せる白磁調の二重箱。蓋を開くと金の飾り罫が現れ、七点が段違いに収まります。</p></div>
    <div class="gs-box__grid">{box_rows}</div>
    <p class="gs-tuning__note">外箱: 218 × 118 × 92mm / 白磁調エンボス紙・金箔押し。数量限定{cfg['limited']['qty']:,}箱、再生産はありません。</p>
  </div>
</section>"""
    return f"""
{_cl_lpnav(cfg, phone)}
<div class="gs-intro" id="gsIntro" aria-hidden="true"><div class="gs-intro__ring">{intro_dots}</div><p class="gs-intro__t">七耀</p></div>
<section class="gs-hero">
  <div class="gs-hero__clouds" aria-hidden="true"><span class="gs-cloud gs-cloud--1"></span><span class="gs-cloud gs-cloud--2"></span><span class="gs-cloud gs-cloud--3"></span></div>
  <div class="gs-hero__frame">
    <p class="gs-hero__eyebrow">{esc(cfg['hero']['eyebrow'])}</p>
    <h1 class="gs-hero__title">{cfg['hero']['title']}</h1>
    <p class="gs-hero__lead">{esc(cfg['hero']['lead'])}</p>
    <div class="gs-hero__tags"><span class="cl-tag">数量限定 {cfg['limited']['qty']:,}台</span><span class="cl-tag">期間限定</span><span class="cl-tag">完全専用設計</span></div>
    <div class="gs-hero__devices">
      <img src="{pimg_front(phone['id'])}" alt="{esc(phone['name'])} 正面" width="240" height="424" loading="eager">
      <img src="{pimg(phone['id'])}" alt="{esc(phone['name'])} 背面(白磁)" width="240" height="424" loading="eager">
    </div>
    <p class="gs-hero__world">{esc(cfg['world'])}</p>
  </div>
</section>

<section class="cl-section gs-terms">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">TEYVAT</p><h2 class="cl-h2">テイワットより。</h2></div>
    <div class="gs-terms__grid">{term_cards}</div>
  </div>
</section>

<section class="cl-section gs-elements" data-elem-stage>
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">SEVEN ELEMENTS</p><h2 class="cl-h2">元素を選ぶと、頁が応える。</h2>
    <p class="cl-lead">背面の元素リング発光を、七元素からプレビューできます。ページの光も、選んだ元素に染まります。</p></div>
    <div class="gs-elem-stage">
      <div class="gs-elem-orb" aria-hidden="true"><img src="{pimg(phone['id'])}" alt="" width="200" height="353" loading="lazy"></div>
      <div class="gs-elems" role="group" aria-label="七元素">{chips}</div>
      <p class="gs-elem-name" aria-live="polite">元素を選んでください</p>
    </div>
  </div>
</section>

<section class="cl-section gs-device">
  <div class="cl-wrap gs-split">
    <div class="gs-split__media reveal"><img src="{pimg(phone['id'], 1)}" alt="{esc(phone['name'])} 金彩" width="280" height="494" loading="lazy"></div>
    <div class="gs-split__copy reveal">
      <p class="cl-eyebrow">CRAFT</p>
      <h2 class="cl-h2">白磁と金彩。<br>工芸品として、仕上げた。</h2>
      <p>SUZAKU 4 の色替えではありません。白磁調の蒸着ガラス、金彩アルミフレーム、背面カメラを囲む元素リング発光層 — 七耀は筐体からゼロ設計のオリジナルです。見る角度で色相がわずかに移ろう仕上げは、原神の元素の揺らぎから起こしました。</p>
      <ul class="cl-points"><li>白磁×金彩のコラボ限定2色</li><li>円形デュアルカメラ+元素リング発光</li><li>厚さ8.7mm・206g</li></ul>
    </div>
  </div>
</section>

<section class="cl-section gs-display">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">ELEMENTAL DISPLAY</p><h2 class="cl-h2">元素燐光ディスプレイ。</h2>
    <p class="cl-lead">色域BT.2020 110%・10bit・ピーク3200nit。テイワットの空の色を、計算で妥協しない。</p></div>
    <div class="gs-gauges">
      <div class="gs-gauge reveal"><b data-cl-count="110">0</b><i>%</i><span>色域 BT.2020</span></div>
      <div class="gs-gauge reveal"><b data-cl-count="3200">0</b><i>nit</i><span>ピーク輝度</span></div>
      <div class="gs-gauge reveal"><b data-cl-count="144">0</b><i>Hz</i><span>可変リフレッシュ</span></div>
      <div class="gs-gauge reveal"><b data-cl-count="7900">0</b><i>mAh</i><span>長時間探索</span></div>
    </div>
  </div>
</section>

<section class="cl-section gs-chip">
  <div class="cl-wrap gs-split gs-split--rev">
    <div class="gs-split__copy reveal">
      <p class="cl-eyebrow">GENSORO-E1</p>
      <h2 class="cl-h2">専用SoC「元素炉」。</h2>
      <p>七耀のために新規設計した3nm SoC。色管理コプロ「幻彩エンジン」をダイに統合し、広色域表示の消費電力を18%削減。AnTuTu 408万点の性能と、旅の長さに応える効率を両立します。</p>
      <div class="gs-vsbar reveal">
        <div class="gs-vsbar__row"><span>SUZAKU 4(雷 RAI-G4)</span><i style="--w:92%"></i><b>385万点</b></div>
        <div class="gs-vsbar__row gs-vsbar__row--hi"><span>七耀(元素炉 GENSORO-E1)</span><i style="--w:97.6%"></i><b>408万点</b></div>
      </div>
      <a class="cl-btn cl-btn--ghost" href="/collab/genshin/silicon/soc/">元素炉 GENSORO-E1 の詳細</a>
    </div>
    <div class="gs-split__media reveal">{svg_art.svg_art('chip', '#2fb9a3')}</div>
  </div>
</section>

<section class="cl-section gs-stats">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">SPEC</p><h2 class="cl-h2">数字で見る、七耀。</h2></div>
    <div class="cl-stats">{_cl_stats(phone)}</div>
    <div style="margin-top:18px"><a class="cl-btn cl-btn--ghost" href="{product_url(phone)}specs/">すべての仕様を見る</a></div>
  </div>
</section>
{gs_ext}
{_cl_silicon(cfg)}
{_cl_accs(cfg, accs)}
{_cl_bundle(cfg)}
{_cl_schedule(cfg)}
{_cl_commerce(cfg, phone)}
{_cl_faq(cfg)}
{_cl_note(cfg)}"""


def _collab_lp_wuwa(cfg, phone, accs):
    """鳴潮「残響」LP — 黒×白の明朝ミニマル・縦書き・スクロール波形。"""
    terms = [
        ("漂泊者", "記憶を失い、ソラリス-3を旅する主人公。残響は、その静かな相棒です。"),
        ("音骸", "戦いのあとに残る、音のかたち。吸収し、力に変える。"),
        ("共鳴者", "特定の事象と共鳴し、その周波数を操る者たち。"),
    ]
    term_cards = "".join(
        f'<div class="ww-term reveal"><h3>{esc(t)}</h3><p>{esc(b)}</p></div>' for t, b in terms)
    bench = [("残響(共振 KYOSHIN-W1)", 418, True), ("SUZAKU 4(雷 RAI-G4)", 385, False),
             ("SUZAKU 3(雷 RAI-G3)", 312, False), ("SUZAKU NEO 2(雷 RAI-G3)", 312, False)]
    bars = "".join(
        f'<div class="ww-bench__row{" ww-bench__row--hi" if hi else ""}"><span>{esc(n)}</span>'
        f'<i style="--w:{v / 4.18:.1f}%"></i><b>{v}万点</b></div>'
        for n, v, hi in bench)

    # --- 追補: タッチ・トゥ・フォトン実測(触れてから光るまで) ---
    lat = [("残響(185Hz・タッチ3200Hz)", 18, True),
           ("SUZAKU 4(175Hz・タッチ2500Hz)", 26, False),
           ("一般的なハイエンド(120Hz)", 45, False)]
    lat_rows = "".join(
        f'<div class="ww-lat__row{" ww-lat__row--hi" if hi else ""}"><span>{esc(n)}</span>'
        f'<i style="--w:{v / 0.45:.0f}%"></i><b>{v}<small>ms</small></b></div>'
        for n, v, hi in lat)

    # --- 追補: 静寂の断面(積層を細線で見せる) ---
    layers = [
        ("0.9mm", "精密鍛造アルミ背板", "マイクロアーク酸化仕上げ。指紋も、音も、残さない。"),
        ("0.3mm", "音叉LED導光層", "背面の唯一の光。音の振幅だけを写す。"),
        ("3.9mm", "両面実装 7,000mAh電池", "基板の裏表に電池を分け、8.2mmの薄さを成立させる。"),
        ("1.9mm", "超薄型旋風ファン", "羽根を非対称ピッチにし、風切り音の山を消した。"),
        ("0.4mm", "ベイパーチャンバー", "熱を面で受け、共振 KYOSHIN-W1 の4.1GHzを支える。"),
    ]
    layer_rows = "".join(
        f'<div class="ww-layer reveal"><b class="ww-layer__mm">{mm}</b>'
        f'<span class="ww-layer__line" aria-hidden="true"></span>'
        f'<span class="ww-layer__body"><b>{esc(t)}</b><small>{esc(d)}</small></span></div>'
        for mm, t, d in layers)

    # --- 追補: 共鳴ハプティクス波形プリセット ---
    presets = [
        ("刃鳴", "M0 20 L8 20 L11 3 L14 34 L17 12 L20 26 L24 20 L60 20 L63 5 L66 32 L70 20 L120 20",
         "パリィの一瞬に、鋭い二段の手応え。立ち上がり0.8ms。"),
        ("水面", "M0 20 Q15 8 30 20 T60 20 T90 20 T120 20",
         "揺れて、減衰する。着水や泳ぎの場面に沈む柔らかい波。"),
        ("心拍", "M0 20 L20 20 L24 10 L28 30 L32 20 L64 20 L68 10 L72 30 L76 20 L120 20",
         "静かな場面の底で脈を打つ、最小振幅の鼓動。"),
        ("無音", "M0 20 L120 20",
         "振動をすべて断つ。音楽と画面だけに集中するための静寂。"),
    ]
    preset_cards = "".join(
        f'<div class="ww-preset reveal"><svg viewBox="0 0 120 40" aria-hidden="true"><path d="{d}" fill="none"/></svg>'
        f'<h3>{esc(t)}</h3><p>{esc(b)}</p></div>'
        for t, d, b in presets)

    # --- 追補: 開発の言葉(縦書き) ---
    words = [
        ("音を足すのは簡単だ。引き算で速さを聴かせるのが、残響の仕事だった。", "共同設計チーム — 音響"),
        ("最速のSoCに、光る箱は要らない。黒い板の中で静かに燃えていればいい。", "共同設計チーム — 筐体"),
        ("漂泊者の旅は長い。だから数字より先に、手に残る静けさを設計した。", "共同設計チーム — 体験"),
    ]
    word_cols = "".join(
        f'<figure class="ww-word reveal"><blockquote>{esc(q)}</blockquote><figcaption>{esc(c)}</figcaption></figure>'
        for q, c in words)

    # --- 追補: 対比の静学(残響 vs SUZAKU 4) ---
    vs_rows = [
        ("AnTuTu", "418万点", "385万点", True),
        ("最大クロック", "4.1GHz", "3.8GHz", True),
        ("リフレッシュレート", "185Hz", "175Hz", True),
        ("タッチサンプリング", "3,200Hz", "2,500Hz", True),
        ("重量", "199g", "229g", True),
        ("厚さ", "8.2mm", "—(通常筐体)", True),
        ("背面の光", "音叉LEDのみ", "ロゴ+LEDスラッシュ", False),
    ]
    vs_html = "".join(
        f'<div class="ww-vs__row reveal"><span class="ww-vs__k">{esc(k)}</span>'
        f'<b class="ww-vs__a{" is-win" if win else ""}">{esc(a)}</b><span class="ww-vs__b">{esc(b)}</span></div>'
        for k, a, b, win in vs_rows)

    ww_ext = f"""
<section class="cl-section ww-lat">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">TOUCH TO PHOTON</p><h2 class="cl-h2">触れてから、光るまで。</h2>
    <p class="cl-lead">指が触れてから画面が応えるまでの実測遅延(当社試験値)。185Hz表示とタッチ3200Hzは、この18msのためにあります。</p></div>
    <div class="ww-lat__chart">{lat_rows}</div>
  </div>
</section>

<section class="cl-section ww-anatomy">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">ANATOMY</p><h2 class="cl-h2">静寂の断面。</h2>
    <p class="cl-lead">8.2mmの内側を、上から順に。速さのための部品だけが、薄く重なっています。</p></div>
    <div class="ww-layers">{layer_rows}</div>
  </div>
</section>

<section class="cl-section ww-hapt">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">RESONANCE HAPTICS</p><h2 class="cl-h2">四つの波形、四つの手応え。</h2>
    <p class="cl-lead">共鳴ハプティクスの専用波形エンジンに、鳴潮のために起こした4プリセットを収録。設定 → サウンドと振動 から切替できます。</p></div>
    <div class="ww-presets">{preset_cards}</div>
  </div>
</section>

<section class="cl-section ww-words">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">WORDS</p><h2 class="cl-h2">開発の言葉。</h2></div>
    <div class="ww-words__row">{word_cols}</div>
  </div>
</section>

<section class="cl-section ww-vs">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">COMPARISON</p><h2 class="cl-h2">対比の静学 — 残響とSUZAKU 4。</h2>
    <p class="cl-lead">旗艦を置き換えるのではなく、別の答えとして。速さに関わる項目だけを、静かに並べます。</p></div>
    <div class="ww-vs__table"><div class="ww-vs__head"><span></span><b>残響</b><span>SUZAKU 4</span></div>{vs_html}</div>
    <a class="cl-btn cl-btn--ghost" href="/products/compare/">比較ツールで全項目を見る</a>
  </div>
</section>"""
    return f"""
{_cl_lpnav(cfg, phone)}
<section class="ww-hero">
  <p class="ww-hero__eyebrow">{esc(cfg['hero']['eyebrow'])}</p>
  <div class="ww-hero__stage">
    <h1 class="ww-hero__title" aria-label="最速は、静けさの中にある。"><span>最速は、</span><span>静けさの中にある。</span></h1>
    <img class="ww-hero__device" src="{pimg(phone['id'])}" alt="{esc(phone['name'])} 漆黒" width="250" height="441" loading="eager">
  </div>
  <p class="ww-hero__lead">{esc(cfg['hero']['lead'])}</p>
  <div class="ww-hero__tags"><span class="cl-tag">数量限定 {cfg['limited']['qty']:,}台</span><span class="cl-tag">SUZAKU史上最速</span><span class="cl-tag">完全専用設計</span></div>
  <canvas class="ww-wave" id="wwWave" aria-hidden="true"></canvas>
</section>

<section class="cl-section ww-world">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">SOLARIS-3</p><h2 class="cl-h2">音の残る世界で。</h2>
    <p class="cl-lead">{esc(cfg['world'])}</p></div>
    <div class="ww-terms">{term_cards}</div>
  </div>
</section>

<section class="cl-section ww-bench">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">KYOSHIN-W1</p><h2 class="cl-h2">全SUZAKUの、頂点。</h2>
    <p class="cl-lead">専用SoC「共振 KYOSHIN-W1」— 最大4.1GHz・AnTuTu 418万点。フラッグシップSUZAKU 4すら、下に置く。</p></div>
    <div class="ww-bench__chart reveal">{bars}</div>
    <a class="cl-btn cl-btn--ghost" href="/collab/wuwa/silicon/soc/">共振 KYOSHIN-W1 の詳細</a>
  </div>
</section>

<section class="cl-section ww-speed">
  <div class="cl-wrap ww-speed__grid">
    <div class="ww-speed__cell reveal"><b data-cl-count="185">0</b><i>Hz</i><span>表示リフレッシュ</span></div>
    <div class="ww-speed__cell reveal"><b data-cl-count="3200">0</b><i>Hz</i><span>タッチサンプリング</span></div>
    <div class="ww-speed__cell reveal"><b data-cl-count="418">0</b><i>万点</i><span>AnTuTu(全機種最高)</span></div>
    <div class="ww-speed__cell reveal"><b>8.2</b><i>mm</i><span>漆黒のモノリス</span></div>
  </div>
</section>

<section class="cl-section ww-device">
  <div class="cl-wrap ww-split">
    <div class="ww-split__media reveal"><img src="{pimg(phone['id'], 1)}" alt="{esc(phone['name'])} 月白" width="270" height="476" loading="lazy"></div>
    <div class="ww-split__copy reveal">
      <p class="cl-eyebrow">MONOLITH</p>
      <h2 class="cl-h2">装飾を、すべて削った。</h2>
      <p>残響の筐体に、ゲーミングの記号はありません。精密鍛造アルミのマイクロアーク酸化仕上げ、直線のエッジ、縦列に沈むトリプルカメラ。唯一の光は、音に共鳴して明滅する背面の音叉LEDだけ。速さは、静けさの中にあります。</p>
      <ul class="cl-points"><li>厚さ8.2mm・199g の薄型モノリス</li><li>音に共鳴する音叉LED</li><li>共鳴ハプティクス(専用波形エンジン)</li></ul>
    </div>
  </div>
</section>

<section class="cl-section ww-stats">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">SPEC</p><h2 class="cl-h2">数字で見る、残響。</h2></div>
    <div class="cl-stats">{_cl_stats(phone)}</div>
    <div style="margin-top:18px"><a class="cl-btn cl-btn--ghost" href="{product_url(phone)}specs/">すべての仕様を見る</a></div>
  </div>
</section>
{ww_ext}
{_cl_silicon(cfg)}
{_cl_accs(cfg, accs)}
{_cl_bundle(cfg)}
{_cl_schedule(cfg)}
{_cl_commerce(cfg, phone)}
{_cl_faq(cfg)}
{_cl_note(cfg)}"""


def _collab_lp_nte(cfg, phone, accs):
    """NTE「夜行」LP — チャコール×マゼンタ×ライム・斜体コンデンス・マーキー・夜景。"""
    marq = "SUZAKU × NTE — WELCOME TO HETHEREAU — 夜行 YAKO — LIMITED {qty} UNITS — ".format(qty=f"{cfg['limited']['qty']:,}")
    terms = [
        ("鑑定士", "S", "骨董品店エイボンに籍を置く、異象事件の解決屋。プレイヤーの分身。"),
        ("異象", "A", "ヘロシティで日常的に起こる超常現象。人々はそれと隣り合って暮らす。"),
        ("エイボン", "B", "表向きは骨董品店。その実、異象がらみの依頼を請け負う拠点。"),
    ]
    term_cards = "".join(
        f'<div class="nt-term reveal"><span class="nt-term__rank">{r}</span><h3>{esc(t)}</h3><p>{esc(b)}</p></div>'
        for t, r, b in terms)
    bld = "".join(f'<span class="nt-bldg" style="--h:{h}%;--d:{d}s"></span>'
                  for h, d in [(58, 0.2), (86, 0.5), (44, 0.8), (95, 0.3), (70, 1.1), (52, 0.6),
                               (80, 0.9), (38, 1.3), (90, 0.4), (64, 1.0), (74, 0.7), (48, 1.2)])

    # --- 追補: 夜景ラボ(露出実測) ---
    lab_cells = "".join(
        f'<div class="nt-lab__cell reveal" style="--lc:{c}"><b>{v}</b><i>{u}</i><span>{esc(d)}</span></div>'
        for v, u, d, c in [
            ("1/4", "秒", "手持ち夜景の限界シャッター(OIS+夜景ISP)", "#ff3ea5"),
            ("-35", "%", "低照度ノイズ(前世代比・当社試験値)", "#c8f24a"),
            ("0.9", "秒", "夜景モードの合成待ち時間", "#3fb6ff"),
            ("30", "秒", "三脚いらずの星空モード最長露光", "#b18bff"),
        ])
    expo = [("一般的なハイエンド", 34, ""), ("SUZAKU 4(天眼 RS-2+ 1/1.28型)", 58, ""), ("夜行(夜行センサー 1/0.98型)", 100, "hi")]
    expo_rows = "".join(
        f'<div class="nt-expo__row{" nt-expo__row--hi" if hi else ""}"><span>{esc(n)}</span>'
        f'<i style="--w:{w}%"></i><b>{"基準の2.9倍" if hi else ""}</b></div>'
        for n, w, hi in expo)

    # --- 追補: EL看板カタログ(発光パターン全6種) ---
    signs = [
        ("PULSE", "nt-sign--pulse", "通知に合わせて一拍、静かに脈打つ標準パターン"),
        ("BEAT", "nt-sign--beat", "再生中の音楽のBPMに同期して明滅する"),
        ("RAIN", "nt-sign--rain", "ネオンの雨が上から下へ流れ落ちる"),
        ("WAVE", "nt-sign--wave", "左右へ波が往復する。充電中の残量表示を兼ねる"),
        ("TEXT", "nt-sign--text", "着信名の頭文字をドットで一瞬だけ描く"),
        ("OFF", "nt-sign--off", "すべて消灯。夜行は黒い板に戻る"),
    ]
    sign_cards = "".join(
        f'<div class="nt-sign {cls} reveal"><span class="nt-sign__frame" aria-hidden="true"><em>{t}</em></span>'
        f'<p>{esc(d)}</p></div>'
        for t, cls, d in signs)

    # --- 追補: 夜スナップ講座(鑑定士の三課) ---
    lessons = [
        ("第一課", "看板は白飛びさせない", "ネオン管の中心は輝度が高く、普通のスマホでは白く潰れます。夜行の夜景ISPは看板領域を検出して局所的に露出を落とし、文字の輪郭とガラス管の色を残します。"),
        ("第二課", "路地は影を黒く残す", "夜景モードの多くは影を持ち上げすぎて昼のようになります。夜行は「夜が夜に見える」階調カーブを既定にし、影は影のまま、その中の質感だけを引き出します。"),
        ("第三課", "動くものは連写でなく1枚で", "1/0.98型の受光量は、シャッターを速くする余裕そのものです。歩く人も走る車も、1/125秒で夜のまま止められます。"),
    ]
    lesson_cards = "".join(
        f'<div class="nt-lesson reveal"><span class="nt-lesson__no">{no}</span><h3>{esc(t)}</h3><p>{esc(b)}</p></div>'
        for no, t, b in lessons)

    # --- 追補: エイボン鑑定書 ---
    cert_rows = "".join(
        f'<div class="nt-cert__row"><span>{esc(k)}</span><i aria-hidden="true"></i><b class="nt-cert__rank" style="--rk:{c}">{r}</b><small>{esc(d)}</small></div>'
        for k, r, d, c in [
            ("夜景描写", "S", "1/0.98型+夜景専用ISP。現行SUZAKU最高", "#ff3ea5"),
            ("処理速度", "A", "夜想 YASO-N1 — AnTuTu 410万点", "#c8f24a"),
            ("記録容量", "S", "最大2TB。8Kナイトビデオ対応", "#ff3ea5"),
            ("稼働時間", "A", "7,400mAh・90W急速充電", "#c8f24a"),
            ("携行性", "B+", "218g。大型センサーとELの代償", "#3fb6ff"),
        ])

    # --- 追補: スコアボード(夜行 vs SUZAKU 4) ---
    score_rows = "".join(
        f'<div class="nt-score__row reveal"><span class="nt-score__k">{esc(k)}</span>'
        f'<b class="nt-score__y{" is-win" if win else ""}">{esc(y)}</b><span class="nt-score__s">{esc(s)}</span></div>'
        for k, y, s, win in [
            ("センサーサイズ", "1/0.98型", "1/1.28型", True),
            ("夜景ISP", "2基(1基は夜景専用)", "1基", True),
            ("最大ストレージ", "2TB", "1TB", True),
            ("AnTuTu", "410万点", "385万点", True),
            ("リフレッシュレート", "165Hz", "175Hz", False),
            ("背面の遊び", "ネオンサインEL", "LEDスラッシュ", True),
        ])

    nt_ext = f"""
<section class="cl-section nt-lab">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">NIGHT LAB</p><h2 class="cl-h2">夜景ラボ — 露出の実測。</h2>
    <p class="cl-lead">夜行センサー 1/0.98型の受光量は、そのまま撮影の自由になります。すべて当社試験値。</p></div>
    <div class="nt-lab__grid">{lab_cells}</div>
    <div class="nt-expo reveal">
      <p class="nt-expo__cap">同一夜景での相対受光量(センサー面積×レンズ、当社換算)</p>
      {expo_rows}
    </div>
  </div>
</section>

<section class="cl-section nt-signs">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">EL SIGN CATALOG</p><h2 class="cl-h2">看板カタログ — 発光パターン全6種。</h2>
    <p class="cl-lead">背面ELの点灯パターンは6種類。テーマまたはクイック設定からいつでも掛け替えられます。</p></div>
    <div class="nt-signs__grid">{sign_cards}</div>
  </div>
</section>

<section class="cl-section nt-snap">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">NIGHT SNAP</p><h2 class="cl-h2">夜スナップ講座 — 鑑定士の三課。</h2>
    <p class="cl-lead">ヘロシティの夜を撮り歩くための、夜行チーム直伝の作法。</p></div>
    <div class="nt-lessons">{lesson_cards}</div>
  </div>
</section>

<section class="cl-section nt-cert">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">APPRAISAL</p><h2 class="cl-h2">鑑定書 — 夜行 YAKO。</h2>
    <p class="cl-lead">骨董品店の流儀で、この一台を鑑定しました。</p></div>
    <div class="nt-cert__card reveal">
      <p class="nt-cert__head">EIBON ANTIQUE SHOP — APPRAISAL REPORT <span>No. YAKO-{cfg['limited']['qty']}</span></p>
      {cert_rows}
      <p class="nt-cert__foot">総合評価 <b>S</b> — 「夜を持ち歩く道具として、出色。看板の光を写して減点なし。」</p>
    </div>
  </div>
</section>

<section class="cl-section nt-score">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">SCOREBOARD</p><h2 class="cl-h2">スコアボード — 夜行 vs SUZAKU 4。</h2>
    <p class="cl-lead">昼の王者と、夜の専門家。負けている項目も、正直に灯します。</p></div>
    <div class="nt-score__table"><div class="nt-score__head"><span></span><b>夜行</b><span>SUZAKU 4</span></div>{score_rows}</div>
    <a class="cl-btn cl-btn--ghost" href="/products/compare/">比較ツールで全項目を見る</a>
  </div>
</section>"""
    return f"""
{_cl_lpnav(cfg, phone)}
<section class="nt-hero">
  <div class="nt-hero__inner">
    <p class="nt-hero__eyebrow">{esc(cfg['hero']['eyebrow'])}</p>
    <h1 class="nt-hero__title"><em>YAKO</em><span>ヘロシティの夜を、連れて歩く。</span></h1>
    <p class="nt-hero__lead">{esc(cfg['hero']['lead'])}</p>
    <div class="nt-hero__stickers" aria-hidden="true"><span class="nt-stick nt-stick--1">1/0.98型</span><span class="nt-stick nt-stick--2">2TB</span><span class="nt-stick nt-stick--3">EL BACK</span></div>
    <img class="nt-hero__device" src="{pimg(phone['id'])}" alt="{esc(phone['name'])} 夜想黒" width="250" height="441" loading="eager">
  </div>
</section>
<div class="nt-marquee" aria-hidden="true"><div class="nt-marquee__track"><span>{esc(marq)}</span><span>{esc(marq)}</span></div></div>

<section class="cl-section nt-world">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">HETHEREAU</p><h2 class="cl-h2">超現実都市へ、ようこそ。</h2>
    <p class="cl-lead">{esc(cfg['world'])}</p></div>
    <div class="nt-terms">{term_cards}</div>
  </div>
</section>

<section class="cl-section nt-city" data-city>
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">NIGHT CITY</p><h2 class="cl-h2">スクロールで、街に灯りが点く。</h2>
    <p class="cl-lead">1/0.98型「夜行センサー」とデュアル夜景ISP。ネオンの滲みも、看板の文字も、路地の階調も。</p></div>
    <div class="nt-cityscape" aria-hidden="true"><div class="nt-city__sky"><span class="nt-moon"></span></div>{bld}<div class="nt-city__road"></div></div>
    <div class="nt-camrow">
      <div class="nt-camcell reveal"><b>1/0.98</b><i>型</i><span>夜行センサー(超大型)</span></div>
      <div class="nt-camcell reveal"><b>2</b><i>基</i><span>ISP(1基は夜景専用)</span></div>
      <div class="nt-camcell reveal"><b>-35</b><i>%</i><span>低照度ノイズ</span></div>
      <div class="nt-camcell reveal"><b>8K</b><i></i><span>ナイトビデオ</span></div>
    </div>
  </div>
</section>

<section class="cl-section nt-el">
  <div class="cl-wrap nt-split">
    <div class="nt-split__media reveal">
      <img src="{pimg(phone['id'], 1)}" alt="{esc(phone['name'])} ネオン桃" width="260" height="459" loading="lazy">
    </div>
    <div class="nt-split__copy reveal">
      <p class="cl-eyebrow">NEON SIGN EL</p>
      <h2 class="cl-h2">背面が、看板になる。</h2>
      <p>背面に埋め込んだEL発光層が、通知・音楽・着信に合わせてネオンサインのように明滅します。発光パターンはテーマから切替可能。ボタンでプレビューできます。</p>
      <div class="nt-elbtns" role="group" aria-label="EL発光パターン">
        <button type="button" class="nt-elbtn is-on" data-el="pulse">PULSE</button>
        <button type="button" class="nt-elbtn" data-el="beat">BEAT</button>
        <button type="button" class="nt-elbtn" data-el="rain">RAIN</button>
        <button type="button" class="nt-elbtn" data-el="off">OFF</button>
      </div>
      <div class="nt-elpanel" data-elpanel aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></div>
    </div>
  </div>
</section>

<section class="cl-section nt-chip">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">YASO-N1 + 2TB</p><h2 class="cl-h2">夜のための、専用シリコン。</h2>
    <p class="cl-lead">専用SoC「夜想 YASO-N1」はISPを2基搭載(1基は夜景デノイズ専用)。ストレージ「夜市 YOICHI」は最大2TB — 8Kナイトビデオも撮り切る。</p></div>
    <div class="cl-stats">{_cl_stats(phone)}</div>
    <div style="margin-top:18px" class="nt-ctas"><a class="cl-btn cl-btn--ghost" href="/collab/nte/silicon/soc/">夜想 YASO-N1 の詳細</a><a class="cl-btn cl-btn--ghost" href="{product_url(phone)}specs/">すべての仕様を見る</a></div>
  </div>
</section>
{nt_ext}
{_cl_silicon(cfg)}
{_cl_accs(cfg, accs)}
{_cl_bundle(cfg)}
{_cl_schedule(cfg)}
{_cl_commerce(cfg, phone)}
{_cl_faq(cfg)}
{_cl_note(cfg)}"""


def _collab_lp_endfield(cfg, phone, accs):
    """エンドフィールド「前線」LP — ゲームUIの雰囲気を全面再現した長編構成。
    タイトル画面/拠点マップ/任務/端末ファイル/設備ダイアログ/持続計器/
    共同開発記録/記録画像/同梱テーマ/スカウト購入/資料室 の11画面+FAQ。"""
    lim = cfg["limited"]

    # --- S3 任務: 特徴をタスク行として、同梱物を任務報酬カードとして描く ---
    tasks = [
        ("8,500mAhで、長時間の連続稼働を維持する", "/products/phone/zensen/specs/"),
        ("IP68+MIL-STD-810H 準拠の装甲で現場に耐える", None),
        ("定速ガバナーで30分後fps維持率99%を保つ", "/collab/endfield/silicon/soc/"),
        ("計器窓とターミナルHUDで稼働状態を常時表示する", None),
        ("USB-C 18W逆給電で現場機器に電力を送る", None),
    ]
    task_rows = "".join(
        (f'<li class="ef-task"><span class="ef-task__box" aria-hidden="true"></span>'
         + (f'<a href="{href}">{esc(t)}</a>' if href else f'<span>{esc(t)}</span>') + "</li>")
        for t, href in tasks)
    rewards = [
        ("ケース", "専用ケース(耐衝撃)", "×1", "#f2d800"),
        ("BOX", "コレクターズボックス", "×1", "#8a8a92"),
        ("CODE", "限定ギフトコード", "×1", "#c86428"),
        ("THEME", "ターミナル・テーマ", "×1", "#4a7ac8"),
        ("EXP", "持続99%", "", "#d43a2e"),
    ]
    reward_cards = "".join(
        f'<div class="ef-reward" style="--rar:{c}"><span class="ef-reward__ic">{k}</span>'
        f'<span class="ef-reward__n">{n}</span><b class="ef-reward__c">{q}</b></div>'
        for k, n, q, c in rewards)

    # --- S2 拠点マップ: 端末内部を「拠点」として読む(円形等高線+黄エリア) ---
    zones = [
        ("中枢エリア", "基幹 KIKAN-F1", "#efMission"),
        ("電力区画", "8,500mAh", "#efOper"),
        ("冷却坑道", "機関 定速ファン", "#efSustain"),
    ]
    zone_tags = "".join(
        f'<a class="ef-map__zone" href="{href}"><i>◎</i>{z}<small>{d}</small></a>'
        for z, d, href in zones)
    left_menu = [
        ("任", "任務", "#efMission"), ("端", "端末ファイル", "#efOper"),
        ("耐", "耐久試験", "#efDura"), ("購", "購買部", "#buy"),
    ]
    left_btns = "".join(
        f'<a class="ef-map__mbtn" href="{href}"><b>{ic}</b><span>{label}</span></a>'
        for ic, label, href in left_menu)
    right_slots = [
        ("資料室", "/collab/endfield/silicon/soc/", False),
        ("編成(アクセサリ)", "#efAcc", False),
        ("記録画像", "#efGallery", False),
        ("通行証(保証)", "/support/warranty/", False),
        ("第2弾", "/collab/#wave2", False),
    ]
    _lock_svg = ('<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">'
                 '<rect x="5" y="11" width="14" height="9" rx="2" fill="currentColor"/>'
                 '<path d="M8 11V8a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" stroke-width="2"/></svg>')
    right_btns = "".join(
        (f'<span class="ef-map__slot is-lock"><i>{_lock_svg}</i>{label}</span>' if locked else
         f'<a class="ef-map__slot" href="{href}"><i>▣</i>{label}</a>')
        for label, href, locked in right_slots)

    # --- S4 端末ファイル ---
    stats = [
        ("性能", "403", "万点", "AnTuTu(基幹 KIKAN-F1)"),
        ("持続", "99", "%", "30分後fps維持率"),
        ("電池", "8500", "mAh", "全機種最大"),
        ("耐候", "-20〜45", "℃", "動作保証温度"),
    ]
    stat_cells = "".join(
        f'<div class="ef-abil"><span class="ef-abil__l">{l}</span><b class="ef-abil__v">{v}<i>{u}</i></b>'
        f'<span class="ef-abil__d">{d}</span></div>' for l, v, u, d in stats)
    skills = [("計器窓", "背面に電池・温度を常時表示"), ("HUD", "ターミナル調AOD"),
              ("逆給電", "USB-C 18Wで機器へ給電"), ("耐滑", "グローブ/濡れ手タッチ")]
    skill_cells = "".join(
        f'<div class="ef-skill"><span class="ef-skill__orb">{t[0]}</span><span class="ef-skill__n">{t}</span>'
        f'<span class="ef-skill__d">{d}</span></div>' for t, d in skills)
    traits = [
        ("特性・定速", "負荷を先読みしてクロックを一定に保ち、フレームタイム分散を48%低減する。"),
        ("特性・岩盤", "高温時はメモリのリフレッシュを強化し、-20〜45℃で仕様通りに動く。"),
        ("特性・坑道", "ストレージの書込耐久は標準比3倍。毎日記録しても摩耗を恐れない。"),
    ]
    trait_rows = "".join(
        f'<div class="ef-trait"><b>{t}</b><span>{d}</span></div>' for t, d in traits)
    slots = "".join(
        f'<a class="ef-slot" href="{collab_silicon_url("endfield", c["key"])}">'
        f'<span class="ef-slot__t">{esc(c["comp"])}</span><b>{esc(c["name"].split(" ")[0])}</b>'
        f'<span class="ef-slot__lv">専用設計</span></a>'
        for c in COLLAB_SILICON["endfield"])

    # --- S5 設備ダイアログ ---
    dura_cards = "".join(
        f'<div class="ef-mat"><span class="ef-mat__t">{esc(k)}</span><span class="ef-mat__v">{esc(v)}</span>'
        f'<b class="ef-mat__own">[PASS]</b></div>'
        for k, v in [("落下", "1.8m × 26方向"), ("防水", "IP68・水深1.5m/30分"),
                     ("防塵", "IP6X+防塵ファン駆動"), ("温度", "-20℃〜45℃"), ("振動・衝撃", "MIL-STD-810H")])

    # --- S6 持続計器: 30分fps推移バー ---
    fps_bars = "".join(
        f'<div class="ef-fpsbar"><i style="--h:{h}"></i><span>{m}分</span></div>'
        for m, h in [(0, 100), (4, 100), (8, 100), (12, 99), (16, 99), (20, 99), (24, 99), (28, 99), (30, 99)])
    boot_lines = [
        "> SUZAKU × ENDFIELD INDUSTRIES — JOINT ENGINEERING",
        "> boot: 基幹 KIKAN-F1 ................ OK",
        "> power cell: 8500mAh ............... 100%",
        "> armor: IP68 / MIL-STD-810H ........ PASS",
        "> thermal: 定速ガバナー .............. ENGAGED",
        "> reverse-power: 18W ................ READY",
        "> ready. 前線、稼働開始。",
    ]
    data_lines = "|".join(boot_lines)

    # --- S7 共同開発記録(スケジュール統合) ---
    devlog = [
        ("2025-08", "プロジェクト起動", "SUZAKUとHypergryphの共同設計チームが発足。「道具として信頼できる端末」を要件の頂点に置く。"),
        ("2025-12", "タロⅡ環境要件を定義", "低温・粉塵・連続稼働の3条件を実機仕様に翻訳。-20℃動作とIP68+MILを必須要件化。"),
        ("2026-04", "基幹 KIKAN-F1 テープアウト", "持続特化の専用SoCの初回試作が完成。定速ガバナーの実測でfps維持率99%を確認。"),
        ("2026-08", "全26項目の耐久試験に合格", "落下26方向・防水・防塵・温度・振動の全項目をパス。装甲リブの最終形状が確定。"),
        ("2026-10-03", "予約受付開始", "SUZAKUストアで先行予約を受付。"),
        ("2026-10-17", "発売", "オンライン・秋葉原直営で同時発売。数量限定6,500台。"),
        ("2026-11-30", "受付終了", "期間限定販売の受付終了。完売次第、期間内でも終了。"),
    ]
    devlog_rows = "".join(
        f'<li class="ef-log reveal"><span class="ef-log__d">{d}</span><b class="ef-log__t">{t}</b>'
        f'<span class="ef-log__b">{b}</span></li>' for d, t, b in devlog)

    # --- S8 記録画像(ギャラリー) ---
    shots = [
        (pimg(phone["id"]), "REC_001 — 黒鉄・背面装甲", f'{esc(phone["name"])} 黒鉄'),
        (pimg(phone["id"], 1), "REC_002 — 工業黄・ハザード", f'{esc(phone["name"])} 工業黄'),
        (pimg_front(phone["id"]), "REC_003 — ターミナルHUD", f'{esc(phone["name"])} 正面'),
    ]
    gallery = "".join(
        f'<figure class="ef-rec reveal"><img src="{src}" alt="{alt}" loading="lazy" width="220" height="388">'
        f'<figcaption>{cap}</figcaption></figure>' for src, cap, alt in shots)

    # --- 追補S12 集成工業システム(端末内部を生産ラインとして描く) ---
    flow_nodes = [
        ("電力", "8,500mAh", "供給 100%", "/products/phone/zensen/specs/"),
        ("制御", "基幹 KIKAN-F1", "定速 3.8GHz", "/collab/endfield/silicon/soc/"),
        ("冷却", "密閉 定速ファン", "IP68内蔵", "/tech/cooling/"),
        ("出力", "144fps 表示", "維持率 99%", "#efSustain"),
    ]
    flow_html = ""
    for i, (t, n, s, href) in enumerate(flow_nodes):
        if i:
            flow_html += '<span class="ef-flow__belt" aria-hidden="true"><i></i><i></i><i></i></span>'
        flow_html += (f'<a class="ef-flow__node" href="{href}"><span class="ef-flow__t">{t}</span>'
                      f'<b>{esc(n)}</b><small>{esc(s)}</small></a>')

    # --- 追補S13 タロⅡ環境モニタ ---
    env_tiles = "".join(
        f'<div class="ef-env__tile reveal"><span class="ef-env__k">{esc(k)}</span><b class="ef-env__v">{v}</b>'
        f'<span class="ef-env__s{" is-warn" if warn else ""}">{tag}</span><small>{esc(d)}</small></div>'
        for k, v, tag, warn, d in [
            ("気温", "-20℃", "動作保証内", False, "寒冷地試験: 電池ヒーター併用で起動・連続稼働を確認"),
            ("気温", "45℃", "動作保証内", False, "高温試験: 定速ガバナーがクロックを保ったまま完走"),
            ("粉塵", "濃度・高", "IP6X", False, "防塵試験: タルク粉8時間曝露後もファン駆動に異常なし"),
            ("降雨", "豪雨相当", "IP68", False, "水深1.5m・30分の浸漬後、全機能の動作を確認"),
            ("落下", "1.8m", "26方向 PASS", False, "コンクリート面への全稜線・全面落下試験"),
            ("振動", "輸送相当", "MIL-STD-810H", True, "装軌車両輸送を模した長時間振動。計器窓の表示乱れなし"),
        ])

    # --- 追補S14 運用記録(通信ログ) ---
    crew_logs = [
        ("REC 06:42", "整備班", "氷点下の朝は、グローブを外した瞬間に指が動かなくなる。前線は手袋のまま全部の操作が通る。計器窓で残量を見て、そのままポケットに戻せるのがいい。"),
        ("REC 13:05", "測量班", "粉塵の多い現場でファン付きは不安だったが、密閉ファンは8時間回しても異音なし。夕方の逆給電で測距計を2回充電した。道具として数に入れられる。"),
        ("REC 21:37", "管理人室", "1日の終わりに残量が残っているかどうかで、翌日の計画が変わる。8,500mAhは数字ではなく、締切前の1時間の余裕として効いている。"),
    ]
    crew_html = "".join(
        f'<div class="ef-crew__log reveal"><span class="ef-crew__rec"><i aria-hidden="true"></i>{t}</span>'
        f'<b class="ef-crew__who">{esc(w)}</b><p>{esc(b)}</p></div>'
        for t, w, b in crew_logs)

    # --- 追補S15 現場運用手順書(SOP) ---
    sop_steps = [
        ("01", "グローブモードの起動", "設定 → 表示 → グローブ操作をON。感圧しきい値が下がり、厚手手袋・濡れ手でのタッチが通ります。"),
        ("02", "計器窓の読み方", "背面の計器窓は上段が電池残量、下段が背面温度。点滅は高温警告 — 直射日光を避けて2分で復帰します。"),
        ("03", "逆給電の手順", "USB-Cを接続し、クイック設定の「給電」をタップ。18Wで測距計・照明・イヤホンへ給電できます(残量20%で自動停止)。"),
        ("04", "現場後の手入れ", "IP68のため水洗い可。ファン吸気口は流水を当ててから振って乾かすだけ。溶剤・超音波洗浄は不可です。"),
    ]
    sop_html = "".join(
        f'<li class="ef-sop__step reveal"><span class="ef-sop__no">{no}</span>'
        f'<div><b>{esc(t)}</b><p>{esc(b)}</p></div></li>'
        for no, t, b in sop_steps)

    # --- 追補S16 補給計画(専用装備の運用表) ---
    supply_rows = "".join(
        f'<a class="ef-supply__row reveal" href="{href}"><span class="ef-supply__cat">{esc(c)}</span>'
        f'<b>{esc(n)}</b><span class="ef-supply__use">{esc(u)}</span><i class="ef-supply__st">{s}</i></a>'
        for c, n, u, s, href in [
            ("電力", "ZENSEN PACK(モバイルバッテリー)", "長期行動日の予備電力。マグネット吸着で歩きながら充電", "配備可", "/products/accessories/pb-endfield/"),
            ("防護", "前線 アーマーケース", "装甲リブに噛み合う二重装甲。単体でもMIL準拠", "配備可", "/products/accessories/cs-endfield/"),
            ("通信", "前線 フィールドバッズ", "騒音下の通話用。骨伝導センサー+IP57", "配備可", "/products/accessories/bd-endfield/"),
        ])

    ef_ext = f"""
<section class="ef-factory" aria-label="集成工業システム">
  <div class="cl-wrap">
    <p class="ef-slash">集成工業システム — 端末内部ライン</p>
    <p class="ef-base__lead">前線の内部を、ひとつの生産ラインとして読む。電力から表示まで、各工程が定速で流れ続けます。</p>
    <div class="ef-flow">{flow_html}</div>
    <p class="ef-flow__note">ラインは負荷を先読みして流量を一定に保つ「定速ガバナー」で管理。工程間の詰まり(サーマルスロットリング)を許容しません。</p>
  </div>
  <span class="ef-meta" aria-hidden="true">SZ-ZENSEN-{lim['qty']} / FACTORY LINE</span>
</section>

<section class="ef-env" aria-label="環境モニタ">
  <div class="cl-wrap">
    <p class="ef-slash ef-slash--w">タロⅡ環境モニタ</p>
    <p class="ef-base__lead">タロⅡ級の環境を想定した全26項目の試験から、代表6項目の記録を表示しています。</p>
    <div class="ef-env__grid">{env_tiles}</div>
  </div>
  <span class="ef-meta" aria-hidden="true">SZ-ZENSEN-{lim['qty']} / ENV MONITOR</span>
</section>

<section class="ef-crew" aria-label="運用記録">
  <div class="cl-wrap">
    <p class="ef-slash">運用記録 — 現場交信ログ</p>
    <p class="ef-base__lead">先行配備の試験運用から、3件の交信記録を抜粋(社内モニター運用・脚色なし)。</p>
    <div class="ef-crew__grid">{crew_html}</div>
  </div>
</section>

<section class="ef-sop" aria-label="現場運用手順書">
  <div class="cl-wrap">
    <p class="ef-slash ef-slash--y">現場運用手順書 — FIELD SOP</p>
    <p class="ef-base__lead">配備初日に読む4項目。道具は、正しい手順で強くなります。</p>
    <ol class="ef-sop__list">{sop_html}</ol>
  </div>
  <span class="ef-meta" aria-hidden="true">SZ-ZENSEN-{lim['qty']} / FIELD SOP</span>
</section>

<section class="ef-supply" aria-label="補給計画">
  <div class="cl-wrap">
    <p class="ef-slash">補給計画 — 専用装備の運用表</p>
    <div class="ef-supply__table">{supply_rows}</div>
  </div>
</section>"""

    return f"""
{_cl_lpnav(cfg, phone)}
<section class="ef-title" aria-label="SUZAKU × アークナイツ: エンドフィールド 前線">
  <div class="ef-title__noise" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
  <img class="ef-title__sil" src="{pimg(phone['id'])}" alt="" aria-hidden="true" width="230" height="406">
  <nav class="ef-title__menu" aria-label="ページ内メニュー">
    <a href="{product_url(phone)}"><span class="ef-title__mi">製</span>製品詳細</a>
    <a href="{product_url(phone)}specs/"><span class="ef-title__mi">仕</span>仕様</a>
    <a href="/collab/endfield/silicon/soc/"><span class="ef-title__mi">基</span>専用シリコン</a>
    <a href="#buy"><span class="ef-title__mi">購</span>購入</a>
  </nav>
  <div class="ef-title__lock">
    <p class="ef-title__over">{esc(cfg['hero']['eyebrow'])}</p>
    <span class="ef-title__rule" aria-hidden="true"></span>
    <h1 class="ef-title__logo"><small>SUZAKU × アークナイツ: エンドフィールド</small><span class="ef-title__band"><em>前線</em><b class="ef-title__box">共同<br>設計</b></span></h1>
    <span class="ef-title__rule" aria-hidden="true"></span>
    <p class="ef-title__lead">{esc(cfg['hero']['lead'])}</p>
  </div>
  <a class="ef-title__continue" href="#efBase">スクロールして続ける <b>▶</b></a>
  <span class="ef-title__ver" aria-hidden="true">SZ_WEB_REL_2026.10_ZENSEN_E{lim['qty']}</span>
  <span class="ef-title__maker" aria-hidden="true">SUZAKU × ENDFIELD INDUSTRIES</span>
</section>

<section class="ef-base" id="efBase" aria-label="拠点マップ">
  <div class="cl-wrap">
    <p class="ef-slash ef-slash--w">拠点 — 前線の内部</p>
    <p class="ef-base__lead">工業機「前線」を、ひとつの拠点として読む。中央のエリアを選ぶと各区画の詳細へ移動します。</p>
    <div class="ef-base__grid">
      <div class="ef-base__left">{left_btns}</div>
      <div class="ef-map" aria-hidden="false">
        <div class="ef-map__ring"></div>
        <div class="ef-map__zonebg" aria-hidden="true"></div>
        <div class="ef-map__zones">{zone_tags}</div>
        <p class="ef-map__lv"><i>●</i> 区画マップ <b>03</b>/03</p>
      </div>
      <div class="ef-base__right">{right_btns}</div>
    </div>
    <div class="ef-base__foot">
      <div class="ef-opcard">
        <span class="ef-opcard__pow">⏻</span>
        <div><b>前線 ZENSEN</b><span class="ef-opcard__lv">稼働状態 <i>99/100</i><em class="ef-opcard__bar"><i></i></em></span></div>
        <span class="ef-opcard__uid">UID:SZ-{lim['qty']}</span>
      </div>
      <p class="ef-toast" role="status">計測レポート「持続99%」を公開中です → <a href="#efSustain">持続計器で見る</a></p>
      <span class="ef-base__mark" aria-hidden="true">ZENSEN</span>
    </div>
  </div>
  <span class="ef-meta" aria-hidden="true">SZ-ZENSEN-{lim['qty']} / BASE MAP</span>
</section>

<section class="ef-mission" id="efMission" aria-label="任務">
  <div class="cl-wrap">
    <p class="ef-slash">調達計画</p>
    <div class="ef-mission__grid">
      <div class="ef-rail2" aria-hidden="true"><span class="is-on">ALL</span><span>◆</span><span>▲</span><span>◇</span><span>▽</span></div>
      <div class="ef-mlist">
        <p class="ef-mlist__urgent"><b>受注</b>共同設計プロジェクト</p>
        <div class="ef-mitem is-on"><span class="ef-mitem__t">前線、受注開始</span><span class="ef-mitem__meta">受付中 ◎ 〜{esc(lim['until'][5:10]).replace('-', '/')}</span></div>
        <div class="ef-mitem"><span class="ef-mitem__t">タロⅡ 環境試験</span><span class="ef-mitem__meta">完了 — 全26項目 PASS</span></div>
        <div class="ef-mitem"><span class="ef-mitem__t">基幹 KIKAN-F1 実装</span><span class="ef-mitem__meta">完了 — 持続99%達成</span></div>
        <div class="ef-mitem"><span class="ef-mitem__t">専用アクセサリ配備</span><span class="ef-mitem__meta">進行中 → 購買部</span></div>
      </div>
      <div class="ef-mdetail">
        <button class="ef-x" type="button" aria-hidden="true" tabindex="-1">✕</button>
        <h2 class="ef-mdetail__t">前線、受注開始</h2>
        <p class="ef-mdetail__area"><i>◎</i> 中枢エリア — SUZAKUストア</p>
        <p class="ef-mdetail__b">{esc(cfg['world'])} タロⅡ級の環境に耐えるよう共同設計した堅牢機「前線」の受注を開始した。下記の導入チェックリストを確認し、受付終了までに手配を。</p>
        <ul class="ef-tasks">{task_rows}</ul>
        <p class="ef-mdetail__rw">同梱物</p>
        <div class="ef-rewards">{reward_cards}</div>
      </div>
    </div>
    <span class="ef-meta" aria-hidden="true">SZ-ZENSEN-{lim['qty']} / PROCUREMENT</span>
  </div>
</section>

<section class="ef-oper" id="efOper" aria-label="端末ファイル">
  <span class="ef-water" aria-hidden="true">Z E N S E N</span>
  <div class="cl-wrap ef-oper__grid">
    <div class="ef-oper__left">
      <p class="ef-slash">端末ファイル</p>
      <h2 class="ef-oper__name">前線<small>ZENSEN</small></h2>
      <p class="ef-oper__stars">JOINT ENGINEERING MODEL — 完全専用設計</p>
      <div class="ef-oper__tags"><span>IP68</span><span>MIL-STD-810H</span><span>工業設計</span><span>共同設計</span></div>
      <p class="ef-oper__cap">キースペック <i>FIELD DATA</i></p>
      <div class="ef-abils">{stat_cells}</div>
      <p class="ef-oper__cap">専用機能 <i>EXCLUSIVE</i></p>
      <div class="ef-skills">{skill_cells}</div>
      <p class="ef-oper__cap">設計特性 <i>TRAITS</i></p>
      <div class="ef-traits">{trait_rows}</div>
    </div>
    <div class="ef-oper__right">
      <div class="ef-level"><b>99</b><span>SUSTAIN / 100</span><i class="ef-level__badge">JOINT ENGINEERING</i></div>
      <div class="ef-oper__ctas"><a class="ef-pill" href="{product_url(phone)}specs/"><span class="ef-pill__dash"></span>仕様を見る<b>+</b></a>
      <a class="ef-pill" href="/products/compare/"><span class="ef-pill__dash"></span>比較する<b>+</b></a></div>
    </div>
    <div class="ef-band">
      <span class="ef-band__txt" aria-hidden="true">SUZAKU × ENDFIELD INDUSTRIES</span>
      <div class="ef-slots">{slots}</div>
    </div>
  </div>
  <span class="ef-meta" aria-hidden="true">SZ-ZENSEN-{lim['qty']} / DEVICE FILE</span>
</section>

<section class="ef-dialog" id="efDura" aria-label="耐久試験">
  <div class="cl-wrap">
    <div class="ef-dlg">
      <div class="ef-dlg__head"><span class="ef-dlg__ic">⚙</span><span class="ef-dlg__cap">// 耐久 <i>DURABILITY</i></span><h2 class="ef-dlg__t">過酷環境テスト</h2><button class="ef-x" type="button" aria-hidden="true" tabindex="-1">✕</button></div>
      <div class="ef-dlg__body">
        <div class="ef-dlg__icon" aria-hidden="true"><span class="ef-dlg__tri">!</span></div>
        <div class="ef-dlg__info">
          <p class="ef-dlg__cap2">試験詳細 <i>TEST REPORT</i></p>
          <p class="ef-dlg__b">この端末はタロⅡ級の過酷環境を想定して設計されている。全26項目の耐久試験に合格済み — 落下も、粉塵も、氷点下も、この装甲の想定内だ。現場での運用に、相当の信頼を置けるだろう。</p>
          <p class="ef-dlg__cap2">試験項目 <i>PASSED</i></p>
          <div class="ef-mats">{dura_cards}</div>
        </div>
      </div>
      <div class="ef-dlg__foot">
        <span class="ef-dlg__warn">⚠ MIL-STD-810H 準拠</span>
        <a class="ef-pill ef-pill--go" href="{product_url(phone)}specs/"><span class="ef-pill__dash"></span>詳細仕様<b>◔</b></a>
      </div>
    </div>
  </div>
</section>

<section class="ef-sustain2" id="efSustain" aria-label="持続性能">
  <div class="cl-wrap">
    <p class="ef-slash ef-slash--y">SUSTAINED 99%</p>
    <h2 class="ef-h2x">落ちない性能を、計器で見る。</h2>
    <p class="ef-leadx">専用SoC「基幹 KIKAN-F1」の定速ガバナーは、発熱を先読みしてクロックを一定に保つ。30分連続負荷でのfps維持率99%は、全SUZAKU製品で最高。瞬間の最速より、8時間後の確実さを選んだ設計です。</p>
    <div class="ef-gauges2">
      <div class="ef-gauge2"><b data-cl-count="99">0</b><i>%</i><span>30分後fps維持率</span></div>
      <div class="ef-gauge2"><b data-cl-count="8500">0</b><i>mAh</i><span>電池(全機種最大)</span></div>
      <div class="ef-gauge2"><b data-cl-count="403">0</b><i>万点</i><span>AnTuTu</span></div>
      <div class="ef-gauge2"><b>-20〜45</b><i>℃</i><span>動作保証温度</span></div>
    </div>
    <div class="ef-fps">
      <p class="ef-fps__cap">144fps 上限・30分連続負荷でのfps推移(当社試験値)</p>
      <div class="ef-fps__bars">{fps_bars}</div>
    </div>
    <div class="ef-terminal" data-terminal data-lines="{esc(data_lines)}"><pre class="ef-terminal__out" aria-label="起動ログ"></pre></div>
  </div>
</section>

<section class="ef-devlog" aria-label="共同開発記録">
  <div class="cl-wrap">
    <p class="ef-slash">共同開発記録</p>
    <p class="ef-base__lead">2025年8月のチーム発足から発売まで — 前線が「道具」になるまでの記録。</p>
    <ol class="ef-logs">{devlog_rows}</ol>
  </div>
</section>

<section class="ef-gallery" id="efGallery" aria-label="記録画像">
  <div class="cl-wrap">
    <p class="ef-slash">記録画像</p>
    <div class="ef-recs">{gallery}</div>
  </div>
</section>

<section class="ef-theme" aria-label="同梱テーマ">
  <div class="cl-wrap ef-theme__grid">
    <div class="ef-theme__media reveal"><img src="{pimg_front(phone['id'])}" alt="ターミナル・テーマパックのHUD表示" width="230" height="406" loading="lazy"></div>
    <div class="ef-theme__copy">
      <p class="ef-slash">同梱テーマ — ターミナル・テーマパック</p>
      <p class="ef-base__lead">SUZAKU OS「陣」に、工業ターミナル調の専用テーマを同梱。起動のたびにシステムチェックが走り、常時表示(AOD)は稼働計器になります。</p>
      <ul class="ef-tasks">
        <li class="ef-task"><span class="ef-task__box"></span><span>専用ロック画面・アイコン・起動音・壁紙</span></li>
        <li class="ef-task"><span class="ef-task__box"></span><span>ターミナル調AOD(温度・クロック・稼働時間)</span></li>
        <li class="ef-task"><span class="ef-task__box"></span><span>計器風ウィジェット / 起動時システムチェック演出</span></li>
        <li class="ef-task"><span class="ef-task__box"></span><span>限定ギフトコード(デモ表記)を同梱</span></li>
      </ul>
      <a class="ef-pill" href="/os/v4/"><span class="ef-pill__dash"></span>SUZAKU OS 4.0 を見る<b>+</b></a>
    </div>
  </div>
</section>

<section class="ef-scout" id="buy" aria-label="数量限定販売">
  <span class="ef-water ef-water--w" aria-hidden="true">Z E N S E N</span>
  <div class="cl-wrap ef-scout__grid">
    <div class="ef-scout__art" data-clview-scope>
      <p class="ef-slash">数量限定販売</p>
      <img class="clview-img" src="{pimg(phone['id'])}" data-back-src="{pimg(phone['id'])}" data-front-src="{pimg_front(phone['id'])}" alt="{esc(phone['name'])} 黒鉄" width="230" height="406" loading="lazy">
      <img src="{pimg(phone['id'], 1)}" alt="{esc(phone['name'])} 工業黄" width="230" height="406" loading="lazy">
      <div class="cl-view" role="group" aria-label="表示切替">
        <button type="button" class="cl-view__btn is-on" data-clview="back" aria-pressed="true">背面</button>
        <button type="button" class="cl-view__btn" data-clview="front" aria-pressed="false">正面</button>
      </div>
    </div>
    <div class="ef-scout__panel">
      <h2 class="ef-scout__t">数量限定<br>販売</h2>
      <p class="ef-scout__pick">対象端末 — 前線 ZENSEN</p>
      <div class="cl-count ef-scout__count" data-until="{lim['until']}" role="timer" aria-label="受付終了までの残り時間">
        <p class="ef-scout__cl">受付終了まで <b data-c="d">--</b>日 <b data-c="h">--</b>:<b data-c="m">--</b>:<b data-c="s">--</b></p>
        <p class="ef-scout__end">終了: {esc(lim['until'][:10].replace('-', '/'))} 23:59 (JST)</p>
      </div>
      <ul class="ef-scout__sure">
        <li>{lim['qty']:,}台以内 — 数量限定生産・完売次第終了</li>
        <li>全数に専用ケース(耐衝撃)同梱 確定</li>
        <li>高コスパ設定 — 同性能帯の想定より抑えた {yen(phone['price'])}</li>
      </ul>
      <div class="cl-stock ef-scout__stock" data-slug="endfield" data-qty="{lim['qty']}" data-sold="{lim['sold']}">
        <div class="cl-stock__bar"><span class="cl-stock__fill"></span></div>
        <p class="cl-stock__meta"><b class="cl-stock__remain">--</b> / {lim['qty']:,} 台 が販売可能</p>
      </div>
      <div class="ef-scout__btns">
        <a class="ef-pill" href="{product_url(phone)}"><span class="ef-pill__dash"></span>製品ページ<b>→</b></a>
        <a class="ef-pill ef-pill--buy" href="{product_url(phone)}#buy"><span class="ef-pill__dash"></span>購入へ {yen(phone['price'])}<b>¥</b></a>
      </div>
    </div>
  </div>
  <div class="ef-scout__bar" aria-hidden="true"><span>◎ アクセサリ</span><span>▣ バンドル</span><span>△ 比較</span><span>✕ 特設一覧</span></div>
</section>

<div id="efAcc">{_cl_accs(cfg, accs)}</div>
{ef_ext}
<section class="ef-archive" aria-label="資料室">
  <div class="cl-wrap">
    <p class="ef-slash">資料室</p>
    <div class="ef-arch__grid">
      <a class="ef-arch" href="/collab/endfield/silicon/soc/"><span class="ef-arch__no">01</span><b>基幹 KIKAN-F1</b><span>持続特化の専用SoC</span></a>
      <a class="ef-arch" href="/collab/endfield/silicon/gpu/"><span class="ef-arch__no">02</span><b>重工 JUKO-GX</b><span>持続クロック固定GPU</span></a>
      <a class="ef-arch" href="/collab/endfield/silicon/mem/"><span class="ef-arch__no">03</span><b>岩盤 GANBAN</b><span>高信頼リフレッシュのメモリ</span></a>
      <a class="ef-arch" href="/collab/endfield/silicon/ssd/"><span class="ef-arch__no">04</span><b>坑道 KODO</b><span>TBW 3倍の高耐久ストレージ</span></a>
      <a class="ef-arch" href="{product_url(phone)}specs/"><span class="ef-arch__no">05</span><b>完全仕様書</b><span>寸法・通信・カメラの全記載</span></a>
      <a class="ef-arch" href="/collab/"><span class="ef-arch__no">06</span><b>コラボ一覧</b><span>七耀 / 残響 / 夜行 / 前線</span></a>
    </div>
  </div>
</section>

{_cl_faq(cfg)}
{_cl_note(cfg)}"""


def _collab_lp_teaser(cfg, phone, accs):
    """コラボ第2弾ティザー — 暗闇+スキャンライン+シルエット+発表カウントダウン。
    コラボ相手は未発表のため、固有名詞は一切出さない(ヒントで匂わせるのみ)。"""
    hints = "".join(
        f'<div class="nx-hint reveal"><span class="nx-hint__no">{esc(no)}</span>'
        f'<h2 class="nx-hint__t">{esc(t)}</h2><p class="nx-hint__b">{esc(b)}</p>'
        f'<span class="nx-hint__tape" aria-hidden="true">CLASSIFIED</span></div>'
        for no, t, b in cfg.get("hints", []))
    links = "".join(
        f'<a class="nx-past" href="/collab/{c["slug"]}/"><span class="nx-past__no">{i + 1:02d}</span>'
        f'<b>{esc(c["edition"])}</b><span class="nx-past__st">受付中</span></a>'
        for i, c in enumerate([c for c in COLLABS if c.get("active")]))
    reveal = cfg.get("reveal_at", "")
    return f"""
<section class="nx-hero">
  <div class="nx-hero__scan" aria-hidden="true"></div>
  <p class="nx-hero__eyebrow">{esc(cfg['hero']['eyebrow'])}</p>
  <h1 class="nx-hero__title"><span class="nx-q" data-nx-glitch>???</span><small>次の共同設計、進行中。</small></h1>
  <div class="nx-hero__sil reveal">{svg_art.svg_art('silhouette', cfg['tokens']['glow'])}</div>
  <p class="nx-hero__lead">第2弾のコラボレーションが、組み立てラインに載りました。相手も、名前も、まだ言えません。言えるのは — 今回も色替えでは終わらない、ということだけ。</p>
</section>

<section class="cl-section nx-count">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">REVEAL</p><h2 class="cl-h2">発表まで。</h2></div>
    <div class="cl-count nx-count__panel" data-until="{esc(reveal)}" role="timer" aria-label="発表までの残り時間">
      <div class="cl-count__row">
        <span class="cl-count__unit"><b data-c="d">--</b><i>日</i></span>
        <span class="cl-count__unit"><b data-c="h">--</b><i>時間</i></span>
        <span class="cl-count__unit"><b data-c="m">--</b><i>分</i></span>
        <span class="cl-count__unit"><b data-c="s">--</b><i>秒</i></span>
      </div>
      <p class="cl-count__end">{esc(reveal[:10].replace('-', '/'))} 20:00 (JST) 発表予定</p>
    </div>
  </div>
</section>

<section class="cl-section nx-hints">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">TEASER</p><h2 class="cl-h2">三つのヒント。</h2>
    <p class="cl-lead">発表日まで、ここだけの手がかりを。当てられても、まだ答え合わせはしません。</p></div>
    <div class="nx-hints__grid">{hints}</div>
  </div>
</section>

<section class="cl-section nx-pasts">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">SERIES</p><h2 class="cl-h2">第1弾は、受付中。</h2></div>
    <div class="nx-pasts__grid">{links}</div>
    <div style="margin-top:22px"><a class="cl-btn cl-btn--ghost" href="/news/">発表はニュースでお知らせします</a></div>
  </div>
</section>
{_cl_note(cfg)}"""


_COLLAB_LP_BUILDERS = {
    "genshin": _collab_lp_genshin,
    "wuwa": _collab_lp_wuwa,
    "nte": _collab_lp_nte,
    "endfield": _collab_lp_endfield,
    "next": _collab_lp_teaser,
}

# 明色ベースのLP(ヘッダー/フッターのテーマを合わせる)
_COLLAB_THEME = {"genshin": "light", "wuwa": "dark", "nte": "dark", "endfield": "light"}


def build_collab_page(cfg):
    """コラボ特設LP。作品ごとに完全個別のレイアウト関数で生成する。"""
    slug = cfg["slug"]
    phone = next((p for p in ALL_PRODUCTS if p["id"] == cfg["phone_id"]), None)
    accs = [p for p in ALL_PRODUCTS if p["id"] in cfg.get("accessory_ids", [])]
    is_teaser = cfg.get("motif") == "teaser"
    builder = _collab_lp_teaser if is_teaser else _COLLAB_LP_BUILDERS[slug]
    body = builder(cfg, phone, accs)
    if is_teaser:
        title = cfg.get("teaser_title", "コラボレーション第2弾 ティザー — COMING SOON")
        desc = cfg.get("teaser_desc", "SUZAKUコラボレーション第2弾のティザーページ。発表カウントダウンと三つのヒントを公開中。相手は、まだ言えません。")
    else:
        title = f"{cfg['edition']} — 公式コラボレーション"
        desc = f"SUZAKU × {cfg['game']} 完全専用設計のコラボレーションモデル「{cfg['edition']}」特設ページ。{cfg['hero']['lead']}"
    render_page(f"/collab/{slug}/", title,
                desc, body, theme=_COLLAB_THEME.get(slug, "dark"), crumbs=None, group="コラボレーション",
                layout="collab", collab=cfg)


def build_collab_hub():
    cards = ""          # 第1弾(受付中)
    wave2_cards = ""    # 第2弾ティザー(相手非公開)
    for cfg in COLLABS:
        tok = cfg["tokens"]
        style = f"--cl-accent:{tok['accent']};--cl-accent2:{tok['accent2']};--cl-bg2:{tok['bg2']}"
        if cfg.get("active"):
            cards += (
                f'<a class="collab-card" style="{style}" href="/collab/{cfg["slug"]}/">'
                f'<span class="collab-card__game">{esc(cfg["game"])}</span>'
                f'<span class="collab-card__edition">{esc(cfg["edition"])}</span>'
                f'<span class="collab-card__tag">数量限定・期間限定 — 受付中</span>'
                f'<span class="collab-card__go">特設ページへ →</span></a>')
        elif cfg.get("motif") == "teaser":
            reveal_ym = cfg.get("reveal_at", "")[:7].replace("-", ".")
            reveal_tag = f"近日公開 — {reveal_ym} 発表予定" if reveal_ym else "近日公開 — ティザー公開中"
            wave2_cards += (
                f'<a class="collab-card collab-card--soon" style="{style}" href="/collab/{cfg["slug"]}/">'
                f'<span class="collab-card__game">{esc(cfg["game"])}</span>'
                f'<span class="collab-card__edition">{esc(cfg["edition"])}</span>'
                f'<span class="collab-card__tag">{reveal_tag}</span>'
                f'<span class="collab-card__go">ティザーを見る →</span></a>')

    # コラボタブレット予告(第1弾の続き)。ページは未公開のため表示のみ。
    tab_icon = ('<svg viewBox="0 0 48 34" aria-hidden="true" class="collab-tabcard__ic">'
                '<rect x="2" y="2" width="44" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="2.4"/>'
                '<circle cx="9" cy="9" r="2.2" fill="currentColor"/></svg>')
    tab_cards = ""
    for cfg in COLLABS:
        if not cfg.get("active"):
            continue
        tok = cfg["tokens"]
        style = f"--cl-accent:{tok['accent']};--cl-accent2:{tok['accent2']};--cl-bg2:{tok['bg2']}"
        tab_cards += (
            f'<div class="collab-tabcard" style="{style}">'
            f'{tab_icon}'
            f'<span class="collab-tabcard__game">{esc(cfg["game"])}</span>'
            f'<span class="collab-tabcard__name">コラボレーションタブレット</span>'
            f'<span class="collab-tabcard__tag">COMING SOON</span></div>')
    body = f"""
<section class="hero hero--sub">
  <div class="hero__bg hero__bg--glow"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">COLLABORATION</p>
    <h1 class="t-hero">コラボレーションモデル</h1>
    <p class="t-lead" style="max-width:680px">人気ゲームタイトルとSUZAKUの共同設計による、数量限定・期間限定のオリジナル端末。色替えではない、筐体・チップ・体験まで専用設計の特別なモデルです。</p>
  </div>
</section>
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">1ST WAVE — 受付中</p><h2 class="t-h2">第1弾 — 4作品、受付中</h2></div>
    <div class="collab-grid">{cards}</div>
  </div>
</section>
<section class="section--sm" id="wave2">
  <div class="container">
    <div class="section-head"><p class="eyebrow">2ND WAVE — COMING SOON</p><h2 class="t-h2">第2弾 — 進行中の共同設計</h2>
    <p class="t-soft" style="max-width:640px">次の第2弾は複数作品を同時進行中。相手も、名前も、まだ言えません。各ティザーで発表カウントダウンとヒントだけ、先に公開しています。</p></div>
    <div class="collab-grid">{wave2_cards}</div>
  </div>
</section>
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">TABLET — NEXT WAVE</p><h2 class="t-h2">コラボレーションタブレット — 第1弾の続き</h2>
    <p class="t-soft" style="max-width:640px">スマートフォン第1弾の4作品で、タブレットの共同設計が進行中です。大画面ならではの専用意匠で準備しています。</p></div>
    <div class="collab-tabgrid">{tab_cards}</div>
    <p class="t-micro t-faint" style="margin-top:24px;text-align:center">※ 掲載のコラボレーションはすべてデモ用の架空企画です。各作品名・権利は各社に帰属します。</p>
  </div>
</section>
"""
    render_page("/collab/", "コラボレーションモデル — SUZAKU × ゲーム",
                "SUZAKUと人気ゲームタイトルの共同設計によるオリジナル端末。七耀(原神)・残響(鳴潮)・夜行(NTE)・前線(エンドフィールド)。",
                body, "dark", [("コラボレーション", None)], "コラボレーション")


def collab_silicon_url(slug, key):
    return f"/collab/{slug}/silicon/{key}/"


def build_collab_silicon_page(cfg, comp):
    """コラボ専用シリコンの詳細ページ。デザインはLPと同じ作品言語(collab-{slug}.css)。"""
    slug = cfg["slug"]
    name = comp["name"]

    rows = "".join(
        f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in comp["rows"])
    vs_rows = "".join(
        f'<tr><th scope="row">{esc(k)}</th><td>{esc(b)}</td><td class="cl-delta__sel">{esc(s)}</td></tr>'
        for k, b, s in comp["vs"])
    points = "".join(f"<li>{esc(p)}</li>" for p in comp["points"])
    others = "".join(
        f'<a class="cl-chip" href="{collab_silicon_url(slug, c["key"])}">{esc(c["comp"])} {esc(c["name"])}</a>'
        for c in COLLAB_SILICON[slug] if c["key"] != comp["key"])

    body = f"""
{_cl_lpnav(cfg, None)}
<section class="cl-shero">
  <div class="cl-wrap cl-shero__grid">
    <div>
      <p class="cl-eyebrow">DEDICATED SILICON — {esc(cfg['game'])}</p>
      <h1 class="cl-shero__title">{esc(name)}</h1>
      <p class="cl-shero__kick">{esc(comp['kicker'])}</p>
      <p class="cl-lead">{esc(cfg['edition'])} のためだけに新規設計した専用{esc(comp['comp'])}。既存チップの選別・流用ではありません。</p>
      <div class="cl-hero__tags"><span class="cl-tag">完全専用設計</span><span class="cl-tag">{esc(comp['comp'])}</span><span class="cl-tag">{esc(comp['en'])}</span></div>
    </div>
    <div class="cl-shero__art">{svg_art.svg_die(f"{slug}-{comp['key']}", esc(name), esc(comp['en']), cfg['tokens']['glow'], cfg['tokens']['accent2'])}</div>
  </div>
</section>

<section class="cl-section">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">SPEC</p><h2 class="cl-h2">主要スペック</h2></div>
    <div class="cl-delta"><table><tbody>{rows}</tbody></table></div>
  </div>
</section>

<section class="cl-section">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">VS STANDARD</p><h2 class="cl-h2">標準フラッグシップとの違い</h2>
    <p class="cl-lead">SUZAKU 4 世代(雷 RAI-G4 ほか)との比較。別設計のため、性格そのものが異なります。</p></div>
    <div class="cl-delta"><table><thead><tr><th>項目</th><th>標準(SUZAKU 4 世代)</th><th>{esc(name)}</th></tr></thead><tbody>{vs_rows}</tbody></table></div>
  </div>
</section>

<section class="cl-section">
  <div class="cl-wrap">
    <div class="cl-head"><p class="cl-eyebrow">WHY DEDICATED</p><h2 class="cl-h2">なぜ、専用設計なのか。</h2></div>
    <p class="cl-lead" style="max-width:760px">{esc(comp['story'])}</p>
    <ul class="cl-points">{points}</ul>
  </div>
</section>

<section class="cl-section cl-buy">
  <div class="cl-wrap cl-buy__inner">
    <div>
      <p class="cl-eyebrow">{esc(cfg['game'])} コラボ専用シリコン</p>
      <h2 class="cl-h2">{esc(name)}</h2>
    </div>
    <div class="cl-buy__cta">
      <a class="cl-btn cl-btn--primary" href="/collab/{slug}/">{esc(cfg['edition'])} を見る</a>
      <a class="cl-btn cl-btn--ghost" href="/tech/">標準の技術一覧</a>
    </div>
  </div>
</section>

<div class="cl-wrap" style="margin-top:28px">
  <p class="cl-eyebrow">同コラボの他のシリコン</p>
  <div class="cl-chips">{others}</div>
</div>
<div class="cl-backlink"><a href="/collab/silicon/">← すべての専用シリコンを見る</a></div>
"""
    desc = f"{cfg['edition']} 専用の{comp['comp']}「{name}」。{comp['kicker']} 専用設計の理由と標準フラッグシップとの違いを解説。"
    render_page(collab_silicon_url(slug, comp["key"]), f"{name} — SUZAKU × {cfg['game']} 専用シリコン",
                desc, body, theme=_COLLAB_THEME.get(slug, "dark"), crumbs=None, group="コラボレーション",
                layout="collab", collab=cfg)


def build_collab_silicon_hub():
    groups = ""
    for cfg in COLLABS:
        if not cfg.get("active"):
            continue
        tok = cfg["tokens"]
        style = f"--cl-accent:{tok['accent']};--cl-accent2:{tok['accent2']};--cl-bg2:{tok['bg2']}"
        cards = "".join(
            f'<a class="collab-card" style="{style}" href="{collab_silicon_url(cfg["slug"], c["key"])}">'
            f'<span class="collab-card__game">専用{esc(c["comp"])}</span>'
            f'<span class="collab-card__edition">{esc(c["name"])}</span>'
            f'<span class="collab-card__tag">{esc(c["kicker"])}</span>'
            f'<span class="collab-card__go">詳細へ →</span></a>'
            for c in COLLAB_SILICON[cfg["slug"]])
        groups += (
            f'<div class="section-head" style="margin-top:var(--sp-6)"><p class="eyebrow">{esc(cfg["game"])}</p>'
            f'<h2 class="t-h3">{esc(cfg["edition"])} の専用シリコン</h2></div>'
            f'<div class="collab-grid">{cards}</div>')
    body = f"""
<section class="hero hero--sub">
  <div class="hero__bg hero__bg--glow"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">DEDICATED SILICON</p>
    <h1 class="t-hero">コラボ専用シリコン</h1>
    <p class="t-lead" style="max-width:700px">各コラボ端末のためだけに新規設計した、SoC・GPU・メモリ・ストレージ。既存チップの選別や流用ではなく、作品ごとに性格の異なる完全専用設計です。</p>
  </div>
</section>
<section class="section--sm">
  <div class="container">{groups}
    <p class="t-micro t-faint" style="margin-top:28px;text-align:center">※ 掲載の数値・設計はデモ用の架空コンテンツです。標準の各技術は<a href="/tech/">テクノロジー</a>をご覧ください。</p>
  </div>
</section>
"""
    render_page("/collab/silicon/", "コラボ専用シリコン — SUZAKU × ゲーム",
                "各コラボ端末専用に新規設計したシリコン(SoC/GPU/メモリ/ストレージ)一覧。元素炉・共振・夜想・基幹ほか。",
                body, "dark", [("コラボレーション", "/collab/"), ("専用シリコン", None)], "コラボレーション")


def build_collab_pages():
    build_collab_hub()
    build_collab_silicon_hub()
    for cfg in COLLABS:
        if cfg.get("active"):
            build_collab_page(cfg)
            for comp in COLLAB_SILICON[cfg["slug"]]:
                build_collab_silicon_page(cfg, comp)
        elif cfg.get("motif") == "teaser":
            build_collab_page(cfg)  # 第2弾ティザー(カウントダウン+シルエット・相手非公開)


# ==========================================================================
# 製品ハブ
# ==========================================================================

def build_line_section(cat, line_key, blurb):
    line = LINES[line_key]
    items = sorted([p for p in ALL_PRODUCTS if p["cat"] == cat and p["line"] == line_key], key=lambda x: -x["year"])
    if not items:
        return ""
    cards = "".join(product_card(p) for p in items)
    cols = min(4, max(2, len(items)))
    return f"""
<section class="section--sm" id="{line_key}">
  <div class="container">
    <div class="section-head"><p class="eyebrow">{line['label']}</p>
    <h2 class="t-h2">{'コラボレーション モデル' if line_key == 'collab' else (esc(items[0]['name'].rsplit(' ', 1)[0]) + ' シリーズ' if line_key != 'suzaku' else 'SUZAKU シリーズ')}</h2>
    <p class="t-soft">{blurb}</p></div>
    <div class="grid grid--{cols} grid--cards reveal-stagger">{cards}</div>
  </div>
</section>"""


def quick_table(cat):
    """現行モデルの早見表(仕様データから自動生成)。"""
    items = sorted([p for p in ALL_PRODUCTS if p["cat"] == cat and p["status"] == "current"],
                   key=lambda x: -x["price"])
    rows = ""
    for p in items:
        rows += f"""<tr>
<td><a href="{product_url(p)}">{esc(p['name'])}</a><br><small class="t-faint">{LINES[p['line']]['label']}</small></td>
<td>{yen(p['price'])}〜</td>
<td>{esc(get_spec(p, ['ディスプレイ'], 'パネル'))}</td>
<td>{esc(get_spec(p, ['性能'], 'SoC').split('(')[0])}</td>
<td>{esc(get_spec(p, ['バッテリー'], 'バッテリー容量').split('(')[0])}</td>
<td>{esc(get_spec(p, ['本体'], '重量'))}</td>
</tr>"""
    return f"""
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">QUICK REFERENCE</p><h2 class="t-h2">現行モデル早見表</h2>
    <p class="t-soft t-small">価格はすべて税込。詳細は各製品名のリンク、より詳しい比較は<a href="/products/compare/" style="color:var(--accent);text-decoration:underline">比較ツール</a>へ。</p></div>
    <div class="scroll-x reveal"><table class="spec-table quick-table">
      <thead><tr><th scope="col">モデル</th><th scope="col">価格</th><th scope="col">ディスプレイ</th><th scope="col">SoC</th><th scope="col">バッテリー</th><th scope="col">重量</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
  </div>
</section>"""


def build_product_hubs():
    # スマートフォンハブ
    body = f"""
<section class="hero hero--sub">
  <div class="hero__bg hero__bg--glow"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">SMARTPHONES</p>
    <h1 class="t-hero">スマートフォン</h1>
    <p class="t-lead" style="max-width:660px">頂点のゲーミングから、毎日のスタンダードまで。4つのライン、すべての世代。</p>
    <div class="hero__actions">
      <a class="btn btn--soft btn--sm" href="#suzaku">SUZAKU</a>
      <a class="btn btn--soft btn--sm" href="#neo">Neo</a>
      <a class="btn btn--soft btn--sm" href="#tsubame">TSUBAME</a>
      <a class="btn btn--soft btn--sm" href="#lite">Lite</a>
      <a class="btn btn--soft btn--sm" href="#collab">コラボ</a>
      <a class="btn btn--ghost btn--sm" href="/products/compare/">比較する</a>
    </div>
  </div>
</section>
{build_line_section('phone', 'collab', '人気ゲームタイトルとの数量限定・期間限定コラボレーション。筐体からSoCまで各作品のためだけに新規設計した、完全オリジナルの限定モデル。')}
{build_line_section('phone', 'suzaku', '自社SoC・多層冷却・独自OSのすべてを注ぎ込む、SUZAKUの旗艦ライン。2023年の初代から毎年更新。')}
{build_line_section('phone', 'neo', '前年フラッグシップの技術を受け継ぎ、価格を抑えたゲーミングスタンダード。「去年の頂点を、今年の普通に」。')}
{build_line_section('phone', 'tsubame', 'ゲーミングで培った技術を日常へ。軽さ・カメラ・電池持ちを磨いた一般向けライン。')}
{build_line_section('phone', 'lite', '3万円台から、SUZAKU品質。はじめての一台にも2台目にも応えるエントリーライン。')}
{quick_table('phone')}
{cta_band('迷ったら、比較ツールへ。', '全12機種をスペックで並べて比較できます。', [('製品を比較する', '/products/compare/', 'btn--primary'), ('ストアで見る', '/store/', 'btn--ghost')])}
"""
    render_page("/products/phone/", "スマートフォン — 全ライン・全世代",
                "SUZAKU(ゲーミング旗艦)・Neo(ゲーミングスタンダード)・TSUBAME(スタンダード)・Lite(エントリー)。4ライン全世代のスマートフォン一覧。",
                body, "dark", [("製品", "/products/"), ("スマートフォン", None)], "製品")

    # タブレットハブ
    body = f"""
<section class="hero hero--sub">
  <div class="hero__bg hero__bg--glow"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">TABLETS</p>
    <h1 class="t-hero">タブレット</h1>
    <p class="t-lead" style="max-width:660px">ゲーミングの大画面から、家族のための一枚まで。タブレットも4つのラインで。</p>
  </div>
</section>
{build_line_section('tablet', 'pad', '氷刃冷却とフラッグシップSoCを大画面に解き放つ、ゲーミングタブレットの旗艦。')}
{build_line_section('tablet', 'pad-neo', 'フラッグシップ級SoCを薄型軽量ボディに。持ち出せるゲーミング。')}
{build_line_section('tablet', 't-pad', '動画・学習・ビデオ通話。暮らしの真ん中で活躍するスタンダード。')}
{build_line_section('tablet', 't-pad-lite', '動画と読書に最適化した、気軽なエントリータブレット。')}
{quick_table('tablet')}
{cta_band('タブレットも、ストアで。', '全モデル送料無料。純正アクセサリとの同時購入がおすすめです。', [('ストアで見る', '/store/', 'btn--primary'), ('アクセサリを見る', '/products/accessories/', 'btn--ghost')])}
"""
    render_page("/products/tablet/", "タブレット — 全ライン・全世代",
                "ゲーミングのSUZAKU Pad、スタンダードのTSUBAME Pad。4ライン全世代のタブレット一覧。",
                body, "dark", [("製品", "/products/"), ("タブレット", None)], "製品")

    # アクセサリハブ
    acc_cards = "".join(product_card(p) for p in ACCESSORIES)
    body = f"""
<section class="hero hero--sub">
  <div class="hero__bg hero__bg--glow" style="background:radial-gradient(50% 40% at 50% 70%, rgba(217,164,65,0.22), transparent 70%), var(--bg-deep)"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">ACCESSORIES</p>
    <h1 class="t-hero">純正アクセサリ</h1>
    <p class="t-lead" style="max-width:660px">冷却・操作・音・電力。SUZAKU製品のために設計された、公式アクセサリ。</p>
  </div>
</section>
<section class="section--sm"><div class="container"><div class="grid grid--3 grid--cards reveal-stagger">{acc_cards}</div></div></section>
{cta_band('本体と一緒に、そろえる。', 'ストアなら本体とアクセサリをまとめて購入できます。', [('ストアで見る', '/store/', 'btn--primary')])}
"""
    render_page("/products/accessories/", "純正アクセサリ",
                "氷嵐クーラー、SUZAKU Grip Pro、SUZAKU Buds、雷速チャージャーなど、SUZAKU純正アクセサリの一覧。",
                body, "dark", [("製品", "/products/"), ("アクセサリ", None)], "製品")

    # 製品トップ
    featured = [p for p in ALL_PRODUCTS if p.get("flag") == "new"]
    feat_cards = "".join(product_card(p) for p in featured[:4])
    cat_cards = f"""
<a class="card card--hover reveal" href="/products/phone/">
  <div class="card__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/></svg></div>
  <h2 class="t-h3">スマートフォン</h2><p class="t-small t-soft">4ライン・全12機種。ゲーミングの頂点から3万円台まで。</p><p class="link-arrow">一覧を見る</p></a>
<a class="card card--hover reveal" href="/products/tablet/">
  <div class="card__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2.5"/></svg></div>
  <h2 class="t-h3">タブレット</h2><p class="t-small t-soft">大画面ゲーミングから家族の一枚まで、全6機種。</p><p class="link-arrow">一覧を見る</p></a>
<a class="card card--hover reveal" href="/products/accessories/">
  <div class="card__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.5"/></svg></div>
  <h2 class="t-h3">アクセサリ</h2><p class="t-small t-soft">クーラー、コントローラー、イヤホンなど純正6製品。</p><p class="link-arrow">一覧を見る</p></a>
"""
    body = f"""
<section class="hero hero--sub">
  <div class="hero__bg hero__bg--glow"></div>
  <div class="hero__inner hero-enter">
    <p class="eyebrow eyebrow--center">PRODUCTS</p>
    <h1 class="t-hero">製品</h1>
    <p class="t-lead" style="max-width:640px">すべての製品に、自社シリコンと冷却技術と独自OS。SUZAKUのフルラインナップ。</p>
    <div class="hero__actions"><a class="btn btn--primary btn--lg" href="/store/">ストアで購入する</a><a class="btn btn--ghost btn--lg" href="/products/compare/">比較する</a></div>
  </div>
</section>
<section class="section--sm"><div class="container"><div class="grid grid--3">{cat_cards}</div></div></section>
<section class="section--sm">
  <div class="container">
    <div class="section-head"><p class="eyebrow">2026 NEW</p><h2 class="t-h2">2026年の新製品</h2></div>
    <div class="grid grid--4 grid--cards reveal-stagger">{feat_cards}</div>
  </div>
</section>
{cta_band('どの一台から、始める?', '比較ツールとストアで、あなたの一台を見つけてください。', [('ストアで見る', '/store/', 'btn--primary'), ('比較ツール', '/products/compare/', 'btn--ghost')])}
"""
    render_page("/products/", "製品 — スマートフォン・タブレット・アクセサリ",
                "SUZAKUの全製品ラインナップ。ゲーミングスマートフォン、タブレット、純正アクセサリ。",
                body, "dark", [("製品", None)], "製品")


# ==========================================================================
# クライアントデータ / sitemap / フラグメント
# ==========================================================================

def get_spec(p, group_keys, row_key):
    for g, rows in p["specs"]:
        if any(k in g for k in group_keys):
            for k, v in rows:
                if row_key in k:
                    return v
    return "—"


def build_client_data():
    prods = []
    for p in ALL_PRODUCTS:
        cmp_data = None
        dash = None
        if p["cat"] in ("phone", "tablet"):
            antutu = product_antutu(p)
            cmp_data = {
                "発売日": p["release"],
                "価格": (yen(p["price"]) + "(税込)〜") if p["status"] == "current" else "販売終了",
                "ディスプレイ": get_spec(p, ["ディスプレイ"], "パネル"),
                "リフレッシュレート": get_spec(p, ["ディスプレイ"], "リフレッシュレート"),
                "常時表示(AOD)": product_aod(p),
                "SoC": get_spec(p, ["性能"], "SoC"),
                "AnTuTu": (f"{antutu}万点" if antutu else "—"),
                "GPU": get_spec(p, ["性能"], "GPU"),
                "メモリ": get_spec(p, ["性能"], "メモリ"),
                "ストレージ": get_spec(p, ["性能"], "ストレージ"),
                "冷却方式": get_spec(p, ["冷却"], "冷却システム"),
                "バッテリー": get_spec(p, ["バッテリー", "バッテリー・充電"], "バッテリー容量") or get_spec(p, ["バッテリー", "バッテリー・充電"], "容量"),
                "急速充電": get_spec(p, ["バッテリー", "バッテリー・充電"], "有線充電"),
                "リアカメラ": get_spec(p, ["カメラ"], "リアカメラ"),
                "背面演出": product_back_fx(p),
                "防塵防水": get_spec(p, ["本体"], "防塵防水"),
                "重量": get_spec(p, ["本体"], "重量"),
                "OS更新": get_spec(p, ["ソフトウェア"], "アップデート"),
                "OS": get_spec(p, ["ソフトウェア"], "OS"),
            }
            dash = [d for d in compare_dash(p) if d["v"] is not None]
        prods.append({
            "id": p["id"], "name": p["name"], "kana": p["kana"], "cat": p["cat"],
            "line": p["line"], "lineLabel": LINES[p["line"]]["label"], "year": p["year"],
            "status": p["status"], "flag": p.get("flag"), "price": p["price"],
            "tagline": p["tagline"], "release": p["release"],
            "colors": p["colors"], "storage": p["storage"],
            "img": pimg(p["id"]), "imgFront": pimg_front(p["id"]) if p["cat"] in ("phone", "tablet") else None,
            "url": product_url(p), "cmp": cmp_data, "dash": dash,
            "radar": radar_values(p) if cmp_data else None,
        })
    news = [{"id": n["id"], "date": n["date"], "cat": n["cat"], "title": n["title"],
             "excerpt": n["excerpt"], "url": f"/news/{n['id']}/"} for n in NEWS]
    data = {
        "products": prods,
        "news": news,
        "faq": FAQ,
        "docs": DOCS,
        "glossary": GLOSSARY,
        "history": HISTORY,
        # 管理ボードのコラボ在庫パネル用の要約(既定値。上書きは sz_collab_stock)
        "collabs": [{"slug": c["slug"], "game": c["game"], "edition": c["edition"],
                     "qty": c["limited"]["qty"], "sold": c["limited"]["sold"]}
                    for c in COLLABS if c.get("active")],
        "pages": PAGES,
        "assetV": ASSET_V,
        "tax": 0.10,
        "freeShipping": 5000,
        "shippingFee": 550,
    }
    js = "// 自動生成: scripts/gen.py — 編集しないでください\nwindow.SZ = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    out = ROOT / "data" / "products.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(js, encoding="utf-8")


def build_assets():
    img = ROOT / "assets" / "img"
    (img / "products").mkdir(parents=True, exist_ok=True)
    (img / "favicon.svg").write_text(svg_art.FAVICON, encoding="utf-8")
    # 法人機は一般 ALL_PRODUCTS から分離しているが、ビジュアル生成対象には含める
    for p in ALL_PRODUCTS + BIZ_PRODUCTS:
        # コラボモデルなどは製品個別のアクセント色(作品カラー)を優先する
        glow = p.get("glow") or LINES[p["line"]]["glow"]
        hz = f"{num(get_spec(p, ['ディスプレイ'], 'リフレッシュレート')) or 60}Hz" if p["cat"] in ("phone", "tablet") else "60Hz"
        # コラボ意匠の出し分け(製品の collab フィールド = 作品slug)
        motif = p.get("collab")
        design = p.get("design")
        for i, c in enumerate(p["colors"]):
            if p["cat"] == "phone":
                svg = svg_art.svg_phone(f"{p['id']}{i}", c["hex"], glow, p["name"], p["kana"], p["line"], hz, design)
            elif p["cat"] == "tablet":
                svg = svg_art.svg_tablet(f"{p['id']}{i}", c["hex"], glow, p["name"], p["kana"], p["line"], hz, design)
            else:
                svg = svg_art.svg_art(p.get("art", "chip"), glow, c["hex"], motif)
            (img / "products" / f"{p['id']}-{i}.svg").write_text(svg, encoding="utf-8")
            # カメラ構成オプション持ち(法人機)はカメラレス背面も生成する
            if p.get("camera_options") and p["cat"] == "phone":
                nc_design = dict(design or {})
                nc_design["cams"] = 0
                nc = svg_art.svg_phone(f"{p['id']}nc{i}", c["hex"], glow, p["name"], p["kana"], p["line"], hz, nc_design)
                (img / "products" / f"{p['id']}-nc-{i}.svg").write_text(nc, encoding="utf-8")
        # デバイスは正面(ディスプレイ点灯)ビューも生成する
        if p["cat"] == "phone":
            front = svg_art.svg_phone_front(p["id"], p["colors"][0]["hex"], glow, p["name"], p["line"], hz, motif, design)
            (img / "products" / f"{p['id']}-front.svg").write_text(front, encoding="utf-8")
            # カメラレス構成は前面カメラも非搭載。正面ビューも穴なしで生成する
            if p.get("camera_options"):
                ncf_design = dict(design or {})
                ncf_design["punch"] = "none"
                ncf = svg_art.svg_phone_front(f"{p['id']}ncf", p["colors"][0]["hex"], glow, p["name"], p["line"], hz, motif, ncf_design)
                (img / "products" / f"{p['id']}-nc-front.svg").write_text(ncf, encoding="utf-8")
        elif p["cat"] == "tablet":
            front = svg_art.svg_tablet_front(p["id"], p["colors"][0]["hex"], glow, p["name"], p["line"], hz, design)
            (img / "products" / f"{p['id']}-front.svg").write_text(front, encoding="utf-8")


def history_timeline_html():
    """沿革タイムラインを HISTORY(単一ソース)からサーバー描画で生成。
    クライアントJS描画だと SEO・no-JS 環境に弱いため、ビルド時にHTMLへ焼き込む。"""
    items = []
    for h in HISTORY:
        news_link = f' <a href="/news/{h["news"]}/">→ 関連ニュース</a>' if h.get("news") else ""
        items.append(
            f'<div class="timeline__item reveal"><p class="timeline__date">{esc(h["date"])}</p>'
            f'<h2 class="t-h4">{esc(h["title"])}</h2>'
            f'<p class="t-small t-soft">{h["body"]}{news_link}</p></div>')
    return "".join(items)


def faq_list_html():
    """FAQ全件をサーバー描画(SEO・no-JS対応)。マークアップは pages.js の
    renderFaq と同一形にし、JS有効時はフィルタ操作でそのまま再描画される。"""
    items = "".join(
        f'<div class="accordion__item"><button class="accordion__q" aria-expanded="false">'
        f'<span><span class="badge" style="margin-right:10px">{esc(f["cat"])}</span>{esc(f["q"])}</span></button>'
        f'<div class="accordion__a"><div class="accordion__a-inner"><div class="accordion__a-body">{f["a"]}</div></div></div></div>'
        for f in FAQ)
    return f'<div class="accordion">{items}</div>'


def news_list_html():
    """ニュース一覧をサーバー描画。JS有効時は年・カテゴリフィルタで再描画される。"""
    items = sorted(NEWS, key=lambda n: n["date"], reverse=True)
    return "".join(
        f'<a class="card card--hover" href="/news/{n["id"]}/">'
        f'<p class="t-micro t-faint">{n["date"].replace("-", ".")} <span class="badge" style="margin-left:8px">{esc(n["cat"])}</span></p>'
        f'<h2 class="t-h4">{esc(n["title"])}</h2>'
        f'<p class="t-small t-soft">{esc(n["excerpt"])}</p>'
        f'<p class="link-arrow">読む</p></a>'
        for n in items)


def glossary_list_html():
    """用語集をサーバー描画(読み順)。JS有効時はカテゴリ/検索で再描画される。"""
    def slug(t):
        return re.sub(r"[^0-9A-Za-z一-龠ぁ-んァ-ヶー]+", "-", t).lower()
    cards = []
    for t in sorted(GLOSSARY, key=lambda x: x["reading"]):
        link = f'<div style="margin-top:10px"><a class="link-arrow" href="{esc(t["link"])}">関連ページを見る</a></div>' if t.get("link") else ""
        cards.append(
            f'<article class="card reveal" id="term-{slug(t["term"])}">'
            f'<div class="spread" style="align-items:baseline;gap:10px"><h2 class="t-h4">{esc(t["term"])} '
            f'<small class="t-faint" style="font-weight:400">{esc(t["reading"])}</small></h2>'
            f'<span class="badge">{esc(t["cat"])}</span></div>'
            f'<p class="t-soft t-small" style="margin-top:8px">{t["desc"]}</p>{link}</article>')
    return "".join(cards)


def build_fragments():
    if not SRC.exists():
        return
    for f in sorted(SRC.rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        m = re.match(r"\s*<!--META\s*(\{.*?\})\s*-->", text, re.S)
        if not m:
            raise SystemExit(f"METAコメントがありません: {f}")
        meta = json.loads(m.group(1))
        body = text[m.end():]
        # ビルド時プレースホルダ(データ駆動セクションのサーバー描画)
        if "<!--HISTORY_TIMELINE-->" in body:
            body = body.replace("<!--HISTORY_TIMELINE-->", history_timeline_html())
        if "<!--FAQ_LIST-->" in body:
            body = body.replace("<!--FAQ_LIST-->", faq_list_html())
        if "<!--NEWS_LIST-->" in body:
            body = body.replace("<!--NEWS_LIST-->", news_list_html())
        if "<!--GLOSSARY_LIST-->" in body:
            body = body.replace("<!--GLOSSARY_LIST-->", glossary_list_html())
        # 図版プレースホルダ <!--ART:kind:glow--> → svg_art 生成(手書き旧図版の一掃用)
        body = re.sub(
            r"<!--ART:([a-z-]+):(#[0-9a-fA-F]{6})-->",
            lambda m2: svg_art.svg_art(m2.group(1), m2.group(2)),
            body)
        rel = f.relative_to(SRC)
        if rel.as_posix() == "home.html":
            url = "/"
        else:
            url = "/" + rel.as_posix()[:-5].removesuffix("/index") + "/"
        if meta.get("root_file"):
            url = "/" + meta["root_file"]
        render_page(url, meta["title"], meta["desc"], body,
                    meta.get("theme", "dark"),
                    [tuple(c) for c in meta.get("crumbs", [])] or None,
                    meta.get("group", "その他"),
                    noindex=meta.get("noindex", False))


def build_sitemap():
    urls = "".join(f"<url><loc>{BASE_URL}{p['url']}</loc></url>" for p in PAGES)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
        encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")


def build_svg_gallery():
    """SVG全点検グリッド(開発者向け・noindex)。全機種の背面+正面ペアと
    アクセサリ全カラーバリエーションを1ページで目視点検できる。"""
    pairs = ""
    for p in PHONES + TABLETS:
        pairs += (
            f'<figure class="svgg-pair"><div class="svgg-pair__imgs">'
            f'<img src="{pimg(p["id"])}" alt="{esc(p["name"])} 背面" loading="lazy" width="250" height="441">'
            f'<img src="{pimg_front(p["id"])}" alt="{esc(p["name"])} 正面" loading="lazy" width="250" height="441">'
            f'</div><figcaption>{esc(p["name"])} <code>{p["id"]}</code></figcaption></figure>')
    accs = ""
    for a in ACCESSORIES:
        for i, c in enumerate(a["colors"]):
            accs += (
                f'<figure class="svgg-acc"><img src="{pimg(a["id"], i)}" alt="{esc(a["name"])} {esc(c["name"])}" loading="lazy" width="480" height="360">'
                f'<figcaption>{esc(a["name"])} — {esc(c["name"])} <code>{a["id"]}-{i}</code></figcaption></figure>')
    body = f"""
<style>
.svgg-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 18px; }}
.svgg-pair, .svgg-acc {{ margin: 0; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); padding: 14px; }}
.svgg-pair__imgs {{ display: flex; gap: 8px; }}
.svgg-pair__imgs img, .svgg-acc img {{ width: 100%; height: auto; min-width: 0; }}
.svgg-pair figcaption, .svgg-acc figcaption {{ margin-top: 8px; text-align: center; font-size: 0.82rem; color: var(--text-soft); }}
.svgg-pair figcaption code, .svgg-acc figcaption code {{ color: var(--accent); }}
</style>
<section class="section">
  <div class="container">
    <div class="section-head"><p class="eyebrow">DESIGN QA</p><h1 class="t-h1">SVG全点検グリッド</h1>
    <p class="t-lead">全デバイスの背面+正面ペア({len(PHONES) + len(TABLETS)}機種)と、アクセサリ全カラーバリエーション({sum(len(a["colors"]) for a in ACCESSORIES)}点)の製品ビジュアル一覧。デザイン監査用の内部ページです。</p></div>
    <h2 class="t-h3" style="margin-bottom:16px">デバイス — 背面 + 正面</h2>
    <div class="svgg-grid">{pairs}</div>
    <h2 class="t-h3" style="margin:32px 0 16px">アクセサリ — 全バリエーション</h2>
    <div class="svgg-grid">{accs}</div>
  </div>
</section>"""
    render_page("/dev/svg-gallery/", "SVG全点検グリッド(内部QA)",
                "全機種の背面・正面と全アクセサリのSVGビジュアルを一覧点検する開発者向け内部ページ。",
                body, "dark", [("ホーム", "/"), ("開発者向け", "/developers/"), ("SVG全点検", None)],
                "開発者向け", noindex=True)


def main():
    build_assets()
    build_svg_gallery()
    for p in ALL_PRODUCTS:
        build_product_page(p)
    for t in TECHS:
        build_tech_page(t)
    for hub in TECH_HUBS:
        build_tech_hub(hub)
    build_os_pages()
    build_news_pages()
    build_collab_pages()
    build_product_hubs()
    for p in BIZ_PRODUCTS:
        build_biz_product_page(p)
    build_biz_os_page()
    build_biz_store()
    build_fragments()
    build_client_data()  # PAGES確定後
    build_sitemap()
    print(f"生成完了: {len(PAGES)}ページ")


if __name__ == "__main__":
    main()
