// 指标解读：市场通用口径、传导影响、观察重点、相关机构观点
// 观点为人工摘录，链接指向公开来源；stance 为与面板当前判断的一致性
window.__IND_VIEWS__ = {
  cpi: {
    benchmark: "市场以 2% 为通胀目标中枢，重点看核心 CPI（剔食品能源）与猪周期；CPI-PPI 剪刀差用于判断利润在上下游之间的分配。",
    impact: "通胀低位打开货币宽松空间、利好债市；上行超预期则压制估值、利好上游周期与通胀受益资产。",
    watch: "下月 CPI 同比、核心 CPI、食品与非食品分项",
    views: [
      { org: "申万宏源（赵伟）", date: "2026-11-10", stance: "一致",
        view: "关注 PPI-CPI 剪刀差收敛，供给侧出清是主要线索。",
        note: "面板 CPI 0.7% 与 PPI 5.7%，剪刀差仍大，收敛尚未发生。",
        link: "https://stcn.com/article/detail/4333001.html" }
    ]
  },
  m1_m2_gap: {
    formula: "剪刀差 = M1 同比 − M2 同比（收窄=资金活化，扩大=资金淤积在定期）",
    benchmark: "市场把 M1−M2 剪刀差作为资金活化的核心指标：收窄代表企业活期存款回升、投资与消费意愿改善；扩大代表宽货币未转化为宽信用。",
    impact: "剪刀差收窄领先权益市场与地产销售；扩大则说明流动性停留在金融体系，实体融资需求偏弱。",
    watch: "下月 M1、M2 同比与剪刀差方向；居民存款与理财搬家",
    views: [
      { org: "中国银河宏观", date: "2026-11-13", stance: "部分一致",
        view: "M1-M2 剪刀差由 -4.0% 收窄至 -2.7%；但 M1 回升主要靠低基数扰动，资金活化实质改善有限。",
        note: "与面板 -2.7pp 一致；面板按 3/6 月均线仍标恶化，方向与该判断一致。",
        link: "https://stock.stockstar.com/JC2026111300042872.shtml" }
    ]
  },
  ppi_cpi_gap: {
    formula: "剪刀差 = PPI 同比 − CPI 同比（正值=上游价格强于下游）",
    benchmark: "市场口径为 PPI 同比减 CPI 同比：正值=上游价格强于下游、利润向上游集中；负值=中下游成本压力缓解、利润向下游转移。通常看方向与绝对水平，不单看正负。",
    impact: "剪刀差扩大利好上游资源与周期品，挤压中下游制造与消费；收窄则相反。与库存周期、工业企业利润配合判断利润分配与通胀传导。",
    watch: "下月 PPI 与 CPI 同比、剪刀差方向；PPI 见顶往往对应剪刀差收敛",
    views: [
      { org: "申万宏源（赵伟）", date: "2026-11-10", stance: "时点差",
        view: "供给侧关注 PPI-CPI 剪刀差收敛。",
        note: "面板剪刀差 5.0pp 且单月扩大 0.9pp，收敛尚未出现，属于预期与现实的时点差。",
        link: "https://stcn.com/article/detail/4333001.html" },
      { org: "国金证券（尹睿哲）", date: "2026年", stance: "部分一致",
        view: "PPI 自 2025 年 7 月筑底向上，历史看领先库存低点 5-6 个月。",
        note: "PPI 上行会推高剪刀差，与面板 5.0pp 的扩大方向一致。",
        link: "https://dxpress.gelonghui.com/p/3630642" }
    ]
  },
  ppi: {
    benchmark: "以 0 轴为荣枯分界，PPI 与库存周期高度相关；市场常看 PPI 见底领先库存低点 5-6 个月，并与 CPI 构成剪刀差。",
    impact: "PPI 回升改善上游利润、抬升名义 GDP，是再通胀交易的核心信号；对债市偏空，对周期与资源股偏多。面板按此视角将 PPI 上行计为改善。",
    watch: "下月 PPI 同比、生产资料与生活资料分项、购进价格（PPIRM）",
    views: [
      { org: "国金证券（尹睿哲）", date: "2026年", stance: "部分一致",
        view: "PPI 自 2025 年 7 月筑底向上，历史看领先库存低点 5-6 个月，提示补库临近。",
        note: "面板 PPI 5.7% 已明显回升，方向一致；但库存同比仍在上升，补库是否已发生待验证。",
        link: "https://dxpress.gelonghui.com/p/3630642" },
      { org: "申万宏源（赵伟）", date: "2026-11-10", stance: "一致",
        view: "供给侧关注 PPI-CPI 剪刀差收敛。",
        note: "面板剪刀差约 5pp，处于高位，收敛过程尚未出现。",
        link: "https://stcn.com/article/detail/4333001.html" }
    ]
  },
  pmi_manufacturing: {
    benchmark: "50 为荣枯线；市场更看新订单、新出口订单与生产之差，以及连续 3 个月的方向，而非单月水平。",
    impact: "跌破 50 压制顺周期与周期股；回升至 50 上方通常领先工业增加值与利润改善。",
    watch: "下月制造业 PMI、新订单与新出口订单、原材料库存",
    views: [
      { org: "中国银河宏观", date: "2026-10-31", stance: "一致",
        view: "10 月制造业 PMI 49.3（前值 50.1），重回收缩区间，建筑业 48.0 是主要拖累。",
        note: "与面板 49.3 完全一致，面板已提示荣枯线下方。",
        link: "https://stock.stockstar.com/JC2026103100034428.shtml" },
      { org: "国盛证券（熊园）", date: "2026-10-31", stance: "一致",
        view: "「外需强、内需弱」格局延续，新出口订单 48.7 跌破荣枯线是后续观察点。",
        note: "与面板出口高增、内需偏弱的背离一致。",
        link: "https://stock.finance.sina.com.cn/stock/go.php/vReport_Show/kind/lastest/rptid/847097211727/index.phtml" }
    ]
  },
  pmi_non_manufacturing: {
    benchmark: "50 为荣枯线；建筑业分项对基建与地产投资敏感，服务业分项受居民消费与金融业景气影响。",
    impact: "跌破 50 说明服务业与建筑业同步走弱，压制服务消费与基建链。",
    watch: "下月非制造业 PMI、建筑业与服务业分项、新订单",
    views: [
      { org: "中国银河宏观", date: "2026-10-31", stance: "一致",
        view: "非制造业 49.7（前值 50.2），建筑业 48.0 是主要拖累，服务业恰好落在 50.0。",
        note: "与面板 49.7 一致。",
        link: "https://stock.stockstar.com/JC2026103100034428.shtml" }
    ]
  },
  services_pmi: {
    benchmark: "财新服务业 PMI 样本偏中小与出口导向企业，与官方非制造业 PMI 常出现背离，市场两份对照看。",
    impact: "服务业是就业与消费的主要载体，持续低于 50 会拖累居民收入与消费。",
    watch: "下月财新服务业 PMI 与官方非制造业的差值",
    views: []
  },
  m1_growth: {
    benchmark: "M1 领先实体与权益市场 3-6 个月；核心看 M1−M2 剪刀差，剪刀差收窄代表资金活化。",
    impact: "M1 回升是股市与地产销售的前瞻信号；仅靠低基数回升则信号弱。",
    watch: "下月 M1 同比、M1−M2 剪刀差、M0 与居民存款",
    views: [
      { org: "中国银河宏观", date: "2026-11-13", stance: "部分一致",
        view: "M1 同比 4.4%（前值 3.2%）、M2 7.1%，剪刀差收窄至 -2.7%；但 M1 回升主要靠低基数扰动，资金活化实质改善有限。",
        note: "数值与面板一致；面板按 3/6 月均线仍标「恶化」，与该判断方向一致。",
        link: "https://stock.stockstar.com/JC2026111300042872.shtml" }
    ]
  },
  m2_growth: {
    benchmark: "M2 反映广义货币与信用派生；市场更看 M2 与社融增速的匹配度，以及 M1−M2 剪刀差。",
    impact: "M2 高增但 M1 弱，说明资金淤积在定期存款，宽货币未转化为宽信用。",
    watch: "下月 M2 同比、M1−M2 剪刀差",
    views: [
      { org: "中国银河宏观", date: "2026-11-13", stance: "一致",
        view: "M2 同比 7.1%（前值 7.2%），剪刀差由 -4.0% 收窄至 -2.7%。",
        note: "与面板一致。",
        link: "https://stock.stockstar.com/JC2026111300042872.shtml" }
    ]
  },
  social_financing: {
    benchmark: "市场主导指标是社融存量同比；单月新增波动大，需看 3 个月移动平均与结构（政府债 vs 企业中长期贷款）。",
    impact: "社融扩张领先实体 3-6 个月；政府债主导的社融对实体的拉动力弱于企业信贷。",
    watch: "下月新增社融、政府债券融资、企业中长期贷款同比多增",
    views: [
      { org: "中国银河宏观", date: "2026-11-13", stance: "部分一致",
        view: "社融存量 469.16 万亿、同比 7.2%；政府融资拐点基本确认，企业中长期贷款同比多增。",
        note: "面板仅有滚动 12 个月增量同比（-3.2%）且滞后约 7 个月，口径不同，不能直接对照。",
        link: "https://stock.stockstar.com/JC2026111300042872.shtml" }
    ]
  },
  tsf_rolling_yoy: {
    formula: "滚动 12 个月社融增量之和的同比增速",
    benchmark: "市场通用口径是社融存量同比；滚动增量同比是替代口径，波动更大，需结合存量增速一起看。",
    impact: "信用脉冲收缩预示后续实体需求走弱，但滞后与口径噪声较大。",
    watch: "社融存量同比是否回升、政府债发行节奏",
    views: []
  },
  retail_sales: {
    benchmark: "市场看社零当月同比而非累计，剔除汽车后看可选消费；社零不含服务消费，与居民消费支出交叉验证。",
    impact: "社零是内需最直接的月度温度计，持续低位压制消费与服务业。",
    watch: "下月社零当月同比、除汽车外分项、餐饮收入",
    views: [
      { org: "中信证券（包承超）", date: "2026-11-12", stance: "时点差",
        view: "2027 年 A 股配置围绕稳健回报、出海制造、内需修复、AI 新应用四条主线。",
        note: "「内需修复」是预期，面板社零 1.1% 显示内需仍弱，属于预期差而非数据冲突。",
        link: "https://www.163.com/dy/article/LBIF6K1A0519DDQ2.html" }
    ]
  },
  consumption_expenditure: {
    benchmark: "居民人均消费支出含服务消费，比社零更接近支出法中的居民消费；看累计同比与收入增速之差。",
    impact: "消费支出增速持续低于收入增速，说明居民储蓄倾向上升、消费意愿偏弱。",
    watch: "下季度居民消费支出与可支配收入的增速差",
    views: []
  },
  residential_income: {
    benchmark: "居民收入是消费的源头，市场看实际增速（名义减 CPI）与中位数增速，中位数更能反映普通家庭。",
    impact: "收入增速回落会通过消费传导至内需，是政策发力的关键变量。",
    watch: "下季度居民可支配收入实际增速与中位数",
    views: []
  },
  fixed_asset_investment: {
    benchmark: "市场拆基建、制造业、地产三分项看，并与民间投资对比判断政策与内生的强弱。",
    impact: "固投是总需求的核心，地产拖累大时基建与制造业能否对冲决定经济韧性。",
    watch: "下月固投当月同比、制造业与基建投资",
    views: []
  },
  realestate_investment: {
    benchmark: "地产投资看累计同比与新开工；销售领先投资 6-9 个月，投资滞后确认。",
    impact: "深度负增长拖累固投与上下游（建材、家电、地方财政）。",
    watch: "下月地产投资同比、新开工面积",
    views: [
      { org: "中国银河宏观", date: "2026-10-31", stance: "一致",
        view: "建筑业 48.0% 是 PMI 主要拖累，地产仍在调整、入冬施工转淡。",
        note: "与面板房地产开发投资 -20.6% 的深度收缩一致。",
        link: "https://stock.stockstar.com/JC2026103100034428.shtml" }
    ]
  },
  house_sales_area: {
    benchmark: "商品房销售面积是地产链最领先的月度指标，市场看同比与环比，并与 30 城高频成交交叉验证。",
    impact: "销售企稳是地产投资止跌的前提；持续负增长意味着后续投资仍将下行。",
    watch: "下月销售面积同比、30 城商品房成交",
    views: []
  },
  new_house_price: {
    benchmark: "70 城房价看环比（更敏感）与同比；一线与三线分化是常见结构特征。",
    impact: "房价预期影响居民加杠杆意愿与地方土地财政。",
    watch: "下月 70 城房价环比、一线城市数据",
    views: []
  },
  real_estate_dev: {
    benchmark: "国房景气指数以 100 为景气基准，连续多月低于 100 说明行业景气偏弱。",
    impact: "综合反映地产投资、销售、资金的景气，是地产链的合成温度计。",
    watch: "下月新发布值（当前数据源已滞后）",
    views: []
  },
  exports_yoy: {
    benchmark: "市场看美元计价同比，剔除基数后与韩国出口、PMI 新出口订单、港口吞吐量交叉验证。",
    impact: "外需是当前总需求的主要支撑，出口回落会放大内需不足的影响。",
    watch: "下月出口同比、新出口订单、韩国前 20 日出口",
    views: [
      { org: "华泰证券（易峘）", date: "2026-11-12", stance: "一致",
        view: "增长的三大支撑是新经济、AI 相关资本开支和外需韧性，美元计价出口有望保持两位数增长。",
        note: "与面板出口 35.2% 的高增一致。",
        link: "https://stcn.com/article/detail/4333001.html" },
      { org: "国盛证券（熊园）", date: "2026-10-31", stance: "一致",
        view: "「外需强、内需弱」格局延续，新出口订单跌破荣枯线是后续观察点。",
        note: "与面板外需强内需弱的背离一致。",
        link: "https://stock.finance.sina.com.cn/stock/go.php/vReport_Show/kind/lastest/rptid/847097211727/index.phtml" }
    ]
  },
  trade_balance: {
    benchmark: "贸易差额是净出口的近似，但会因进口下滑而被动扩大，需与出口增速一起看。",
    impact: "顺差被动扩大常伴随内需走弱，对汇率有支撑但结构不健康。",
    watch: "下月进出口同比、顺差结构",
    views: []
  },
  industrial_production: {
    benchmark: "规上工业增加值只覆盖规上企业，市场常与用电量、PMI 生产分项交叉验证。",
    impact: "工业生产是生产法 GDP 的核心月度代理，与需求端背离时提示库存变化。",
    watch: "下月工业增加值同比、高耗能行业分项",
    views: [
      { org: "华泰证券（易峘）", date: "2026-11-12", stance: "部分一致",
        view: "新经济与 AI 相关资本开支是增长的重要支撑。",
        note: "面板工业增加值 5.5% 温和；结构化亮点在细分行业，总量数据难以体现。",
        link: "https://stcn.com/article/detail/4333001.html" }
    ]
  },
  services_production_index: {
    benchmark: "服务业生产指数是第三产业增加值的月度代理，市场与服务业 PMI 交叉验证。",
    impact: "三产占 GDP 过半，服务业生产走弱会直接拖累 GDP。",
    watch: "下月服务业生产指数同比",
    views: []
  },
  electricity: {
    formula: "规模以上工业发电量当月同比（%），与国家统计局工业数据同批发布",
    benchmark: "发电量是工业生产的物理同步指标；与全社会用电量的差异主要来自统计口径与线损。",
    impact: "发电量是工业活动最直接的物理指标，与工业增加值背离时提示结构变化。",
    watch: "下月发电量当月同比、工业增加值与二产用电",
    views: []
  },
  gdp_growth: {
    benchmark: "市场看实际 GDP 同比与名义 GDP（含平减指数），名义增速反映价格与企业盈利环境。",
    impact: "季度 GDP 是周期的锚，Q4 增速决定全年目标能否达成。",
    watch: "下一季度 GDP 同比与平减指数",
    views: [
      { org: "中信证券（明明）", date: "2026-11-12", stance: "时点差",
        view: "2027 年中国经济「波动中复苏」，实际 GDP 增速约 4.5%。",
        note: "面板当前周期阶段为「震荡期」，与「复苏」预期存在时点差。",
        link: "https://stcn.com/article/detail/4333001.html" },
      { org: "华泰证券（易峘）", date: "2026-11-12", stance: "一致",
        view: "预测 2026 年实际/名义 GDP 增 4.6%/5.8%。",
        note: "面板 GDP 4.6% 与该预测一致。",
        link: "https://stcn.com/article/detail/4333001.html" }
    ]
  },
  fiscal_revenue: {
    benchmark: "财政收入增速看税收分项，与名义 GDP 同步；土地出让收入是地方财政的关键变量。",
    impact: "财政减收会限制支出与基建，是财政脉冲的先行约束。",
    watch: "下月财政收入同比、税收与非税分项",
    views: []
  },
  fiscal_expenditure: {
    benchmark: "财政支出看累计同比与支出进度，市场用「财政脉冲」（支出增速减收入增速）判断力度。",
    impact: "支出是政府购买（G）的直接来源，是逆周期调节的主要抓手。",
    watch: "下月财政支出同比与专项债发行、实物工作量形成",
    views: [
      { org: "广发证券（郭磊）", date: "2026-11-12", stance: "一致",
        view: "2026 年政策「跨周期」特征更明显，聚焦挖掘经济潜能、投资于物与人结合。",
        note: "面板财政支出仅 1.0%、政府支出分项 z -0.60，政策力度尚未在数据中体现，与该判断不冲突。",
        link: "https://stock.hexun.com/2026-11-12/225263598.html" }
    ]
  },
  industrial_profit: {
    benchmark: "工业企业利润看累计同比，与 PPI 和库存周期高度相关；市场用「利润-库存」四象限判断库存周期阶段。",
    impact: "利润改善是制造业投资与就业的前提，利润-库存组合决定补库意愿。",
    watch: "下月利润累计同比、产成品存货与营收增速",
    views: [
      { org: "天风证券", date: "2026-02-26", stance: "一致",
        view: "整体处于「需求放缓引导的被动补库」阶段，行业分化明显。",
        note: "面板利润单月回落、存货上升，与被动补库一致。",
        link: "http://vip.stock.finance.sina.com.cn/q/go.php/vReport_Show/kind/lastest/rptid/825425955284/index.phtml" }
    ]
  },
  inventory_growth: {
    benchmark: "库存同比配合营收/利润方向判定主动/被动补库；市场通常看「库存同比 − 营收同比」的剪刀差。",
    impact: "被动补库对应价格下行压力；主动去库结束往往对应周期底部。",
    watch: "下月产成品存货同比与营收增速",
    views: [
      { org: "天风证券", date: "2026-02-26", stance: "一致",
        view: "当前整体处于「需求放缓引导的被动补库」阶段。",
        note: "面板存货同比上升、利润回落，与被动补库一致。",
        link: "http://vip.stock.finance.sina.com.cn/q/go.php/vReport_Show/kind/lastest/rptid/825425955284/index.phtml" },
      { org: "国金证券（尹睿哲）", date: "2026年", stance: "时点差",
        view: "本轮主动去库已持续约 15 个月、接近历史极值，PPI 见底提示补库临近。",
        note: "面板显示库存已在被动累积，与「补库临近」的时点判断存在差异。",
        link: "https://dxpress.gelonghui.com/p/3630642" },
      { org: "湘财证券", date: "2026-09-03", stance: "一致",
        view: "7、8 月被动补库与主动去库行业增多，与宏观短周期「趋向见顶」一致。",
        note: "与面板被动补库判断一致。",
        link: "https://wap.stockstar.com/detail/JC2026090300022362" }
    ]
  },
  unemployment: {
    benchmark: "市场关注青年失业率与 25-59 岁主力人群失业率，总量失业率对周期钝化。",
    impact: "失业率上行压制消费与政策容忍度，是稳增长政策的重要触发条件。",
    watch: "下月城镇调查失业率、青年失业率",
    views: []
  },
  cpi_food: {
    benchmark: "食品项受猪价与菜价扰动，市场看能繁母猪存栏与猪价高频。",
    impact: "食品价格波动对 CPI 影响大但对政策意义小。",
    watch: "猪价与蔬菜批发价",
    views: []
  },
  lpr: {
    benchmark: "LPR 是政策利率，市场看 1Y/5Y 报价与 MLF、存款利率的联动，以及房贷利率加点。",
    impact: "降息直接降低实体融资成本与房贷负担，滞后确认政策取向。",
    watch: "下次 LPR 报价与 MLF 操作",
    views: []
  },
  shibor_overnight: {
    benchmark: "隔夜 Shibor 反映银行间流动性，市场看 DR007 与政策利率的偏离度。",
    impact: "资金面紧张抬升短端利率，压制债市与成长股估值。",
    watch: "隔夜 Shibor、DR007 与逆回购投放",
    views: []
  },
  bond_yield_10y: {
    benchmark: "10Y 国债收益率反映增长与通胀预期；市场看 10Y-1Y 期限利差与中美利差。",
    impact: "长端利率下行利好债券与高股息资产；反映增长预期偏弱。",
    watch: "10Y 收益率、期限利差、资金面",
    views: []
  },
  sh_index: {
    benchmark: "股市领先实体经济约 6 个月，但短期受流动性与风险偏好主导；市场看成交额与估值分位。",
    impact: "股指影响居民财富效应与融资功能，是风险偏好的直接体现。",
    watch: "成交额、估值分位、北向资金",
    views: [
      { org: "中信证券（包承超）", date: "2026-11-12", stance: "时点差",
        view: "2027 年 A 股「K 型收敛、行情宽度拓展」，风格回归价值。",
        note: "策略预期，与面板股指近月偏弱不矛盾。",
        link: "https://www.163.com/dy/article/LBIF6K1A0519DDQ2.html" }
    ]
  },
  margin_sh: {
    benchmark: "沪深融资余额反映两市杠杆资金的风险偏好，市场看其占流通市值比重与变化速率。",
    impact: "融资余额快速上升常伴随市场情绪亢奋，回落则提示去杠杆。",
    watch: "沪深融资余额变化速率与历史分位；融资余额占流通市值比重",
    views: []
  },
  commodity_price_index: {
    benchmark: "商品指数领先 PPI 约 1-3 个月，市场看南华商品指数与原油、铜、螺纹的分化。",
    impact: "商品上行推升 PPI 与上游利润，抬升通胀预期。",
    watch: "商品指数、原油与有色金属价格",
    views: []
  },
  consumer_confidence: {
    benchmark: "消费者信心指数以 100 为中性参考，市场更看趋势与就业预期分项。",
    impact: "信心影响消费意愿，是社零的领先情绪指标。",
    watch: "下月消费者信心指数与就业预期分项",
    views: []
  },
  fx_reserves: {
    benchmark: "外储变动 = 经常/资本项目差额 + 汇率折算 + 资产估值；市场主要看其稳定性与是否接近警戒线。",
    impact: "外储稳定支撑汇率与主权信用；单月波动多为估值因素。",
    watch: "下月外储余额、美元指数与美债收益率",
    views: []
  }
};
