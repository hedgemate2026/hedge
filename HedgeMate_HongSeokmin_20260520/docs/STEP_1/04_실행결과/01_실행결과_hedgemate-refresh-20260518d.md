# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-05-18T03:27:26.938739+00:00
- 데이터 버전(data_version): 20260518
- 분석기간: 2021-05-09 ~ 2026-05-18
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 66일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
- 시나리오 벡터: `scenario_research\outputs\scenario_vectors\current_scenario_vector_final-refresh-20260518b.csv`
- 현재 장세 요약: 현재 장세: 장기금리 부담장(STRESS, us_global, score=77.142012) / 물가·에너지 재상승장(ACTIVE, us_global, score=72.756862) / 달러강세/원화약세장(PROVISIONAL, fx_krw, score=60.402968)
- Active adverse scenario: 장기금리 부담장, 물가·에너지 재상승장, 달러강세/원화약세장, 급성 리스크오프/유동성 경색장, 지정학 확전·공급충격장
- raw 재사용 여부(동일 data_version 재실행): YES
- FX raw 재사용 여부: YES

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
| 1 | USO | commodity_energy | 0.4941 | 1.0000 | 0.0000 | 1.0000 | 0.4371 | 0.1430 | -0.2806 | -0.0602 | 2.7310 | 6142185171507.20 |
| 2 | XLE | commodity_energy | 0.4045 | 0.6118 | 0.5700 | 0.5844 | 0.3143 | 0.3669 | 0.1304 | -0.0338 | 2.0883 | 4556295859594.41 |
| 3 | LQD | bond | 0.3865 | 0.0000 | 0.9650 | 0.7319 | 0.0929 | 0.1005 | 0.7784 | -0.0155 | 0.9291 | 6443095129718.67 |
| 4 | GLD | gold | 0.3728 | 0.2727 | 0.4119 | 0.8192 | 0.2517 | 0.0000 | 0.4896 | -0.0411 | 1.7607 | 7154893833428.98 |
| 5 | DBC | commodity_energy | 0.3411 | 0.7485 | 0.6472 | 0.4042 | 0.4087 | 1.0000 | -0.0142 | -0.0302 | 2.5824 | 72783019017.27 |
| 6 | XLV | defensive | 0.3236 | 0.0425 | 0.8192 | 0.9224 | 0.1178 | 0.6264 | 0.7333 | -0.0223 | 1.0595 | 2718462530082.70 |
| 7 | SHY | bond | 0.3180 | 0.1269 | 1.0000 | 0.8348 | 0.0540 | 0.9253 | 0.6440 | -0.0139 | 0.7258 | 601615478961.41 |
| 8 | TLT | bond | 0.3157 | 0.0676 | 0.9094 | 0.6634 | 0.0000 | 0.4084 | 0.7068 | -0.0181 | 0.4431 | 4262798691194.17 |
| 9 | IEF | bond | 0.3061 | 0.0594 | 0.9824 | 0.7955 | 0.0564 | 0.8130 | 0.7155 | -0.0147 | 0.7386 | 1397129678556.49 |
| 10 | XLU | defensive | 0.2961 | 0.2234 | 0.7346 | 0.7796 | 0.1130 | 0.7747 | 0.5418 | -0.0262 | 1.0345 | 1668197650979.01 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_input_sample.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 추천상태 분포: FAIL_GATE 42, PASS_RECOMMEND 35, REFERENCE_ONLY 49
- 1:1 최적 후보: GLD (최종점수 0.6964, CVaR 개선률 17.95%, Sharpe 개선률 14.51%)
- 다자산 최적 조합: GLD + SHY + IAU (최종점수 0.5718, CVaR 개선률 18.25%, Sharpe 개선률 13.63%)

## 산출 파일
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_market_daily_20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_fx_daily_20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_benchmark_daily_20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\dq_result_hedgemate-refresh-20260518d.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\features_summary_hedgemate-refresh-20260518d.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\metric_validation_hedgemate-refresh-20260518d.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\hes_components_hedgemate-refresh-20260518d.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\asset_risk_sensitivity_hedgemate-refresh-20260518d.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_sensitivity_summary_hedgemate-refresh-20260518d.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\asset_scenario_sensitivity_hedgemate-refresh-20260518d.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_scenario_sensitivity_summary_hedgemate-refresh-20260518d.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_scenario_sensitivity_visual_hedgemate-refresh-20260518d.html`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\recommendation_status_qa_hedgemate-refresh-20260518d.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_1to1_hedge_hedgemate-refresh-20260518d.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_multi_hedge_hedgemate-refresh-20260518d.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_compare_hedgemate-refresh-20260518d.csv`
