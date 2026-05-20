# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-05-20T08:50:51.719965+00:00
- 데이터 버전(data_version): 20260520
- 분석기간: 2007-01-01 ~ 2026-05-20
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 269일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
- 시나리오 벡터: `scenario_research\outputs\scenario_vectors\current_scenario_vector_final-refresh-20260520e2efast.csv`
- 현재 장세 요약: 현재 장세: 장기금리 부담장(STRESS, us_global, score=78.845293) / 달러강세/원화약세장(ACTIVE, fx_krw, score=73.685808) / 물가·에너지 재상승장(ACTIVE, us_global, score=64.455958)
- Active adverse scenario: 장기금리 부담장, 달러강세/원화약세장, 물가·에너지 재상승장, 중국·무역분절 충격장, 급성 리스크오프/유동성 경색장, 지정학 확전·공급충격장
- raw 재사용 여부(동일 data_version 재실행): YES
- FX raw 재사용 여부: YES

## DQ 요약(캘린더 기준)
- PASS: 8
- WARN: 62
- FAIL: 0
- 최소 coverage_ratio_calendar: 0.9666

## 지표 엔진 검증셋
- PASS: 7
- FAIL: 0
- 결측 처리 정책:
  - vol_annual 최소 관측치: 20
  - mdd_1y 최소 관측치: 20
  - var/cvar 최소 관측치: 60
  - beta 최소 교집합 관측치: 60
  - downside beta 최소 하락일: 20
  - corr 최소 관측치: 20

## 헷징 후보 Top 10 (KRW 기준)

| 순위 | 티커 | 버킷 | HES | Corr | CVaR | Stress | Sharpe | LiquidityPenalty | corr_sp500_60d_krw | cvar_95_1y_krw | sharpe_1y_krw_proxy | adv_60 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | XLE | commodity_energy | 0.4175 | 0.6060 | 0.5700 | 0.3257 | 0.7368 | 0.3475 | 0.1325 | -0.0338 | 2.3052 | 4514352933179.83 |
| 2 | LQD | bond | 0.4039 | 0.0000 | 0.9650 | 0.7177 | 0.2032 | 0.0760 | 0.7836 | -0.0155 | 0.9468 | 6362320513297.07 |
| 3 | GLD | gold | 0.3948 | 0.2398 | 0.4119 | 0.7568 | 0.5364 | 0.0000 | 0.5259 | -0.0411 | 1.7950 | 6879693699387.57 |
| 4 | USO | commodity_energy | 0.3842 | 1.0000 | 0.0000 | 0.0000 | 1.0000 | 0.1050 | -0.2909 | -0.0602 | 2.9751 | 6164918368774.20 |
| 5 | TLT | bond | 0.3826 | 0.0595 | 0.9094 | 1.0000 | 0.0000 | 0.3973 | 0.7196 | -0.0181 | 0.4296 | 4175625624321.16 |
| 6 | DBC | commodity_energy | 0.3808 | 0.7517 | 0.6483 | 0.1765 | 0.9700 | 1.0000 | -0.0241 | -0.0302 | 2.8988 | 73595336412.58 |
| 7 | SHY | bond | 0.3486 | 0.1354 | 1.0000 | 0.8745 | 0.1884 | 0.9229 | 0.6381 | -0.0139 | 0.9091 | 598507121135.56 |
| 8 | IEF | bond | 0.3468 | 0.0562 | 0.9824 | 0.9319 | 0.1465 | 0.8082 | 0.7232 | -0.0147 | 0.8024 | 1378840058167.91 |
| 9 | TIP | bond | 0.3121 | 0.1148 | 0.9780 | 0.7611 | 0.1976 | 0.9529 | 0.6602 | -0.0149 | 0.9325 | 394454122760.18 |
| 10 | XLP | defensive | 0.2961 | 0.2058 | 0.8188 | 0.6206 | 0.1680 | 0.7288 | 0.5625 | -0.0223 | 0.8571 | 1919142658012.32 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `HedgeMate\inputs\portfolio_weights.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 추천상태 분포: FAIL_GATE 8, PASS_RECOMMEND 1, REFERENCE_ONLY 13
- 1:1 최적 후보: IAU (최종점수 0.7353, CVaR 개선률 8.71%, Sharpe 개선률 3.13%)

## 산출 파일
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_market_daily_20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_fx_daily_20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_benchmark_daily_20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\dq_result_liquidity-order-smoke-20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\features_summary_liquidity-order-smoke-20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\metric_validation_liquidity-order-smoke-20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\hes_components_liquidity-order-smoke-20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\asset_risk_sensitivity_liquidity-order-smoke-20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_sensitivity_summary_liquidity-order-smoke-20260520.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\asset_scenario_sensitivity_liquidity-order-smoke-20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_scenario_sensitivity_summary_liquidity-order-smoke-20260520.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_scenario_sensitivity_visual_liquidity-order-smoke-20260520.html`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\recommendation_status_qa_liquidity-order-smoke-20260520.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_1to1_hedge_liquidity-order-smoke-20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_multi_hedge_liquidity-order-smoke-20260520.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_compare_liquidity-order-smoke-20260520.csv`
