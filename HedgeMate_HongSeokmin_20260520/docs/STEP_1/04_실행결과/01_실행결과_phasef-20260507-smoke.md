# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-05-07T01:57:43.843597+00:00
- 데이터 버전(data_version): 20260415
- 분석기간: 2021-04-28 ~ 2026-05-07
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 66일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
- 시나리오 벡터: `../scenario_research/outputs/scenario_vectors/current_scenario_vector_phasef-20260507-smoke.csv`
- 현재 장세 요약: 현재 장세: 우호적 위험선호장(ACTIVE, us_global, score=63.775241) / 경기둔화/침체 우려장(WATCH, us_global, score=47.699147) / 물가·에너지 재상승장(WATCH, us_global, score=46.026696)
- raw 재사용 여부(동일 data_version 재실행): YES
- FX raw 재사용 여부: YES

## DQ 요약(캘린더 기준)
- PASS: 5
- WARN: 65
- FAIL: 0
- 최소 coverage_ratio_calendar: 0.9367

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
| 1 | USO | commodity_energy | 0.4210 | 1.0000 | 0.4046 | 0.3498 | 0.9996 | 1.0000 | -0.2607 | -0.0553 | 2.0965 | 5517852658045.20 |
| 2 | DBC | commodity_energy | 0.3867 | 0.7534 | 0.7934 | 0.0000 | 1.0000 | 1.0000 | -0.0096 | -0.0300 | 2.0976 | 56436011861.47 |
| 3 | XLE | commodity_energy | 0.3467 | 0.5754 | 0.7309 | 0.1058 | 0.9929 | 1.0000 | 0.1717 | -0.0341 | 2.0767 | 4863410156722.80 |
| 4 | BTC-USD | crypto | 0.3334 | 0.1311 | 0.4025 | 1.0000 | 0.0000 | 0.0000 | 0.6243 | -0.0554 | -0.8506 | 4051929714418493440.00 |
| 5 | IAU | gold | 0.3034 | 0.4423 | 0.6247 | 0.2437 | 0.9195 | 1.0000 | 0.3073 | -0.0410 | 1.8603 | 2294581078943.17 |
| 6 | GLD | gold | 0.3018 | 0.4434 | 0.6206 | 0.2437 | 0.9137 | 1.0000 | 0.3062 | -0.0413 | 1.8431 | 12256220305335.14 |
| 7 | XLU | defensive | 0.2906 | 0.2638 | 0.8448 | 0.2204 | 0.7959 | 1.0000 | 0.4891 | -0.0267 | 1.4958 | 1866346784075.10 |
| 8 | SHY | bond | 0.2348 | 0.1148 | 1.0000 | 0.2528 | 0.3700 | 1.0000 | 0.6408 | -0.0166 | 0.2402 | 674264021174.51 |
| 9 | IEF | bond | 0.2311 | 0.0955 | 0.9875 | 0.2297 | 0.4292 | 1.0000 | 0.6604 | -0.0174 | 0.4149 | 1588555043793.58 |
| 10 | TIP | bond | 0.2253 | 0.1041 | 0.9867 | 0.1772 | 0.4477 | 1.0000 | 0.6517 | -0.0175 | 0.4692 | 463139032470.09 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `inputs/portfolio_weights.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 1:1 최적 후보: SHY (최종점수 0.6675, CVaR 개선률 9.10%, Sharpe 개선률 0.86%)
- 다자산 최적 조합: IAU + SHY (최종점수 0.7103, CVaR 개선률 8.71%, Sharpe 개선률 4.61%)

## 단일 종목 질의 분석 요약
- 기준 자산: 005930.KS 100%
- 1:1 최적 후보: BTC-USD (예산 10.0%, 최종점수 0.8084)
- 다자산 최적 조합: BTC-USD + XLU (예산 10.0%, 최종점수 0.6520)

## 산출 파일
- `outputs/raw/raw_market_daily_20260415.csv`
- `outputs/raw/raw_fx_daily_20260415.csv`
- `outputs/raw/raw_benchmark_daily_20260415.csv`
- `outputs/reports/dq_result_phasef-20260507-smoke.csv`
- `outputs/processed/features_summary_phasef-20260507-smoke.csv`
- `outputs/reports/metric_validation_phasef-20260507-smoke.csv`
- `outputs/reports/hes_components_phasef-20260507-smoke.csv`
- `outputs/processed/asset_risk_sensitivity_phasef-20260507-smoke.csv`
- `outputs/reports/asset_sensitivity_summary_phasef-20260507-smoke.md`
- `outputs/processed/asset_scenario_sensitivity_phasef-20260507-smoke.csv`
- `outputs/reports/asset_scenario_sensitivity_summary_phasef-20260507-smoke.md`
- `outputs/reports/portfolio_1to1_hedge_phasef-20260507-smoke.csv`
- `outputs/reports/portfolio_multi_hedge_phasef-20260507-smoke.csv`
- `outputs/reports/portfolio_compare_phasef-20260507-smoke.csv`
- `outputs/reports/single_asset_hedge_1to1_phasef-20260507-smoke.csv`
- `outputs/reports/single_asset_hedge_multi_phasef-20260507-smoke.csv`
- `outputs/reports/single_asset_compare_phasef-20260507-smoke.csv`
