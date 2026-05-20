# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-05-18T02:51:17.526952+00:00
- 데이터 버전(data_version): 20260518
- 분석기간: 2021-05-09 ~ 2026-05-18
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 66일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
- 시나리오 벡터: `scenario_research\outputs\scenario_vectors\current_scenario_vector_final-refresh-20260518.csv`
- 현재 장세 요약: 현재 장세: 우호적 위험선호장(ACTIVE, us_global, score=70.844784) / 물가·에너지 재상승장(WATCH, us_global, score=54.52398) / 장기금리 부담장(WATCH, us_global, score=51.616058)
- Active adverse scenario: 물가·에너지 재상승장, 장기금리 부담장
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
| 1 | USO | commodity_energy | 0.5786 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.1430 | -0.2806 | -0.0602 | 2.7310 | 6142185169663.35 |
| 2 | XLE | commodity_energy | 0.4088 | 0.6118 | 0.5700 | 0.3025 | 0.7191 | 0.3669 | 0.1304 | -0.0338 | 2.0883 | 4556295857753.13 |
| 3 | GLD | gold | 0.3969 | 0.2727 | 0.4119 | 0.6966 | 0.5759 | 0.0000 | 0.4896 | -0.0411 | 1.7607 | 7154893831587.26 |
| 4 | LQD | bond | 0.3681 | 0.0000 | 0.9650 | 0.5501 | 0.2124 | 0.1005 | 0.7784 | -0.0155 | 0.9291 | 6443095127863.67 |
| 5 | DBC | commodity_energy | 0.3392 | 0.7485 | 0.6472 | 0.0000 | 0.9351 | 1.0000 | -0.0142 | -0.0302 | 2.5824 | 72783019257.14 |
| 6 | XLV | defensive | 0.3358 | 0.0425 | 0.8192 | 0.8698 | 0.2694 | 0.6264 | 0.7333 | -0.0223 | 1.0595 | 2718462530620.14 |
| 7 | SHY | bond | 0.3060 | 0.1269 | 1.0000 | 0.7227 | 0.1236 | 0.9253 | 0.6440 | -0.0139 | 0.7258 | 601615478383.48 |
| 8 | IEF | bond | 0.2892 | 0.0594 | 0.9824 | 0.6568 | 0.1292 | 0.8130 | 0.7155 | -0.0147 | 0.7386 | 1397129679048.49 |
| 9 | XLU | defensive | 0.2881 | 0.2234 | 0.7346 | 0.6300 | 0.2585 | 0.7747 | 0.5418 | -0.0262 | 1.0345 | 1668197652280.92 |
| 10 | IAU | gold | 0.2759 | 0.2711 | 0.4198 | 0.6967 | 0.5854 | 0.8267 | 0.4912 | -0.0408 | 1.7824 | 1300307006941.46 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_input_sample.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 추천상태 분포: FAIL_GATE 21, PASS_RECOMMEND 13, REFERENCE_ONLY 17
- 1:1 최적 후보: GLD (최종점수 0.6795, CVaR 개선률 17.95%, Sharpe 개선률 14.51%)
- 다자산 최적 조합: GLD + TLT (최종점수 0.3382, CVaR 개선률 9.59%, Sharpe 개선률 5.68%)

## 산출 파일
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_market_daily_20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_fx_daily_20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\raw\raw_benchmark_daily_20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\dq_result_hedgemate-refresh-20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\features_summary_hedgemate-refresh-20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\metric_validation_hedgemate-refresh-20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\hes_components_hedgemate-refresh-20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\asset_risk_sensitivity_hedgemate-refresh-20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_sensitivity_summary_hedgemate-refresh-20260518.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\processed\asset_scenario_sensitivity_hedgemate-refresh-20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_scenario_sensitivity_summary_hedgemate-refresh-20260518.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\asset_scenario_sensitivity_visual_hedgemate-refresh-20260518.html`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\recommendation_status_qa_hedgemate-refresh-20260518.md`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_1to1_hedge_hedgemate-refresh-20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_multi_hedge_hedgemate-refresh-20260518.csv`
- `C:\Users\석민\Documents\cau_2026_ss\금융인공지능실습1\HedgeMate\outputs\reports\portfolio_compare_hedgemate-refresh-20260518.csv`
