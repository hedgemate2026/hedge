# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-05-19T10:36:19.917854+00:00
- 데이터 버전(data_version): 20260519
- 분석기간: 2021-05-10 ~ 2026-05-19
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 66일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
- 시나리오 벡터: `scenario_research\outputs\scenario_vectors\current_scenario_vector_final-refresh-20260519.csv`
- 현재 장세 요약: 현재 장세: 장기금리 부담장(STRESS, us_global, score=76.425412) / 물가·에너지 재상승장(ACTIVE, us_global, score=70.124968) / 달러강세/원화약세장(STRESS, fx_krw, score=65.788718)
- Active adverse scenario: 장기금리 부담장, 물가·에너지 재상승장, 달러강세/원화약세장, 중국·무역분절 충격장, 급성 리스크오프/유동성 경색장, 지정학 확전·공급충격장
- raw 재사용 여부(동일 data_version 재실행): NO
- FX raw 재사용 여부: NO

## DQ 요약(캘린더 기준)
- PASS: 69
- WARN: 1
- FAIL: 0
- 최소 coverage_ratio_calendar: 0.9927

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
| 1 | USO | commodity_energy | 0.5026 | 1.0000 | 0.0000 | 1.0000 | 0.4777 | 0.1272 | -0.2791 | -0.0602 | 2.9065 | 6164029011984.15 |
| 2 | XLE | commodity_energy | 0.4107 | 0.6110 | 0.5700 | 0.5844 | 0.3487 | 0.3582 | 0.1322 | -0.0338 | 2.2412 | 4552150085567.47 |
| 3 | LQD | bond | 0.3882 | 0.0000 | 0.9650 | 0.7319 | 0.0962 | 0.0923 | 0.7782 | -0.0155 | 0.9389 | 6407411200745.11 |
| 4 | GLD | gold | 0.3755 | 0.2832 | 0.4119 | 0.8192 | 0.2522 | 0.0000 | 0.4787 | -0.0411 | 1.7434 | 7051731652254.27 |
| 5 | DBC | commodity_energy | 0.3498 | 0.7555 | 0.6483 | 0.4042 | 0.4537 | 1.0000 | -0.0206 | -0.0302 | 2.7828 | 73760681537.93 |
| 6 | XLV | defensive | 0.3245 | 0.0426 | 0.8192 | 0.9224 | 0.1210 | 0.6241 | 0.7331 | -0.0223 | 1.0670 | 2696994406645.49 |
| 7 | SHY | bond | 0.3219 | 0.1298 | 1.0000 | 0.8348 | 0.0743 | 0.9242 | 0.6409 | -0.0139 | 0.8261 | 602549040985.65 |
| 8 | TLT | bond | 0.3157 | 0.0668 | 0.9094 | 0.6634 | 0.0000 | 0.4070 | 0.7075 | -0.0181 | 0.4427 | 4211576265960.22 |
| 9 | IEF | bond | 0.3079 | 0.0614 | 0.9824 | 0.7955 | 0.0636 | 0.8113 | 0.7132 | -0.0147 | 0.7710 | 1390765216477.68 |
| 10 | XLU | defensive | 0.2965 | 0.2287 | 0.7346 | 0.7796 | 0.1022 | 0.7701 | 0.5364 | -0.0262 | 0.9699 | 1677652113309.88 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_input_sample.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 추천상태 분포: FAIL_GATE 42, PASS_RECOMMEND 35, REFERENCE_ONLY 49
- 1:1 최적 후보: GLD (최종점수 0.6873, CVaR 개선률 17.95%, Sharpe 개선률 14.54%)
- 다자산 최적 조합: GLD + SHY + IAU (최종점수 0.5691, CVaR 개선률 18.25%, Sharpe 개선률 13.67%)

## 산출 파일
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_market_daily_20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_fx_daily_20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_benchmark_daily_20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\dq_result_hedgemate-refresh-20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\features_summary_hedgemate-refresh-20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\metric_validation_hedgemate-refresh-20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\hes_components_hedgemate-refresh-20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\asset_risk_sensitivity_hedgemate-refresh-20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_sensitivity_summary_hedgemate-refresh-20260519.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\asset_scenario_sensitivity_hedgemate-refresh-20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_scenario_sensitivity_summary_hedgemate-refresh-20260519.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_scenario_sensitivity_visual_hedgemate-refresh-20260519.html`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\recommendation_status_qa_hedgemate-refresh-20260519.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_1to1_hedge_hedgemate-refresh-20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_multi_hedge_hedgemate-refresh-20260519.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_compare_hedgemate-refresh-20260519.csv`
