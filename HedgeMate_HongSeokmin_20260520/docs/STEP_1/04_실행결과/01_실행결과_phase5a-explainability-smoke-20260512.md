# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-05-12T06:52:39.805069+00:00
- 데이터 버전(data_version): 20260507
- 분석기간: 2021-05-03 ~ 2026-05-12
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 66일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
- 시나리오 벡터: `../scenario_research/outputs/scenario_vectors/current_scenario_vector_latest-20260507.csv`
- 현재 장세 요약: 현재 장세: 우호적 위험선호장(STRONG, us_global, score=75.158538) / 물가·에너지 재상승장(WATCH, us_global, score=48.464917)
- Active adverse scenario: 물가·에너지 재상승장
- raw 재사용 여부(동일 data_version 재실행): YES
- FX raw 재사용 여부: YES

## DQ 요약(캘린더 기준)
- PASS: 5
- WARN: 65
- FAIL: 0
- 최소 coverage_ratio_calendar: 0.9352

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
| 1 | DBC | commodity_energy | 0.3467 | 0.7424 | 0.7859 | 0.3616 | 0.2825 | 1.0000 | -0.0615 | -0.0288 | 2.8201 | 65253050802.30 |
| 2 | BTC-USD | crypto | 0.3280 | 0.2712 | 0.4198 | 0.7612 | 0.0197 | 0.0000 | 0.6111 | -0.0554 | -0.6772 | 4021387090926819840.00 |
| 3 | 055550.KS | kr_stock | 0.3237 | 0.9463 | 0.6038 | 0.1941 | 0.3156 | 1.0000 | -0.3526 | -0.0420 | 3.2603 | 150537301349.17 |
| 4 | XOM | us_stock | 0.3211 | 0.7247 | 0.6774 | 0.4269 | 0.2343 | 1.0000 | -0.0363 | -0.0367 | 2.1788 | 4962754519948.64 |
| 5 | 017670.KS | kr_stock | 0.3171 | 0.9487 | 0.4870 | 0.3948 | 0.1946 | 1.0000 | -0.3560 | -0.0506 | 1.6506 | 94932231105.00 |
| 6 | USO | commodity_energy | 0.3145 | 0.9143 | 0.3741 | 0.5014 | 0.2812 | 1.0000 | -0.3069 | -0.0588 | 2.8027 | 6085398063016.14 |
| 7 | XLE | commodity_energy | 0.3134 | 0.6474 | 0.7367 | 0.4039 | 0.2443 | 1.0000 | 0.0740 | -0.0323 | 2.3111 | 4722839728305.15 |
| 8 | 068270.KS | kr_stock | 0.3117 | 0.9732 | 0.5141 | 0.3465 | 0.1373 | 1.0000 | -0.3910 | -0.0486 | 0.8877 | 129946692100.00 |
| 9 | 032830.KS | kr_stock | 0.3080 | 0.8809 | 0.4597 | 0.2349 | 0.5061 | 1.0000 | -0.2592 | -0.0525 | 5.7952 | 98260039495.00 |
| 10 | JNJ | defensive | 0.3034 | 0.3987 | 0.8574 | 0.4771 | 0.2932 | 1.0000 | 0.4291 | -0.0235 | 2.9618 | 2843043178697.00 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `inputs/portfolio_weights.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 추천 결과 없음: Gate 통과 후보가 없어 참고안을 표시합니다. 리스크 관리가 어렵습니다.
- 참고안: 참고안(다자산) - TLT + GLD
- 추천상태 분포: FAIL_GATE 2, REFERENCE_ONLY 33

## 단일 종목 질의 분석 요약
- 기준 자산: TSLA 100%
- 추천 결과 없음: Gate 통과 후보가 없어 참고안을 표시합니다. 리스크 관리가 어렵습니다.
- 참고안: 참고안(1:1) - GLD
- 추천상태 분포: FAIL_GATE 1, REFERENCE_ONLY 35

## 산출 파일
- `outputs/raw/raw_market_daily_20260507.csv`
- `outputs/raw/raw_fx_daily_20260507.csv`
- `outputs/raw/raw_benchmark_daily_20260507.csv`
- `outputs/reports/dq_result_phase5a-explainability-smoke-20260512.csv`
- `outputs/processed/features_summary_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/metric_validation_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/hes_components_phase5a-explainability-smoke-20260512.csv`
- `outputs/processed/asset_risk_sensitivity_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/asset_sensitivity_summary_phase5a-explainability-smoke-20260512.md`
- `outputs/processed/asset_scenario_sensitivity_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/asset_scenario_sensitivity_summary_phase5a-explainability-smoke-20260512.md`
- `outputs/reports/asset_scenario_sensitivity_visual_phase5a-explainability-smoke-20260512.html`
- `outputs/reports/recommendation_status_qa_phase5a-explainability-smoke-20260512.md`
- `outputs/reports/portfolio_1to1_hedge_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/portfolio_multi_hedge_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/portfolio_compare_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/single_asset_hedge_1to1_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/single_asset_hedge_multi_phase5a-explainability-smoke-20260512.csv`
- `outputs/reports/single_asset_compare_phase5a-explainability-smoke-20260512.csv`
