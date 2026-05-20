# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-05-07T02:11:29.770133+00:00
- 데이터 버전(data_version): 20260507
- 분석기간: 2021-04-28 ~ 2026-05-07
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 66일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
- 시나리오 벡터: `../scenario_research/outputs/scenario_vectors/current_scenario_vector_latest-20260507.csv`
- 현재 장세 요약: 현재 장세: 우호적 위험선호장(PROVISIONAL, us_global, score=79.943622) / 물가·에너지 재상승장(WATCH, us_global, score=48.464917) / 장기금리 부담장(WATCH, us_global, score=46.248861)
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
| 1 | USO | commodity_energy | 0.3980 | 1.0000 | 0.3151 | 0.3498 | 0.9953 | 1.0000 | -0.3069 | -0.0588 | 2.8027 | 6085398063016.14 |
| 2 | DBC | commodity_energy | 0.3833 | 0.7677 | 0.7657 | 0.0000 | 1.0000 | 1.0000 | -0.0615 | -0.0288 | 2.8201 | 65253050802.30 |
| 3 | XLE | commodity_energy | 0.3383 | 0.6394 | 0.7119 | 0.1058 | 0.8620 | 1.0000 | 0.0740 | -0.0323 | 2.3111 | 4722839728305.15 |
| 4 | BTC-USD | crypto | 0.3318 | 0.1310 | 0.3652 | 1.0000 | 0.0520 | 0.0000 | 0.6111 | -0.0554 | -0.6772 | 4021387090926819840.00 |
| 5 | XLU | defensive | 0.2805 | 0.3392 | 0.8320 | 0.2204 | 0.6243 | 1.0000 | 0.3911 | -0.0243 | 1.4340 | 1750791120607.21 |
| 6 | SHY | bond | 0.2468 | 0.1030 | 1.0000 | 0.2528 | 0.4697 | 1.0000 | 0.6407 | -0.0131 | 0.8637 | 612301506284.08 |
| 7 | TIP | bond | 0.2336 | 0.1064 | 0.9854 | 0.1771 | 0.5014 | 1.0000 | 0.6370 | -0.0141 | 0.9807 | 398662018741.54 |
| 8 | IEF | bond | 0.2306 | 0.0701 | 0.9823 | 0.2297 | 0.4768 | 1.0000 | 0.6755 | -0.0143 | 0.8898 | 1455614805183.26 |
| 9 | XLP | defensive | 0.2142 | 0.2365 | 0.8655 | 0.1270 | 0.4222 | 1.0000 | 0.4997 | -0.0221 | 0.6884 | 2178088117611.65 |
| 10 | LQD | bond | 0.2112 | 0.0000 | 0.9688 | 0.1924 | 0.5368 | 1.0000 | 0.7495 | -0.0152 | 1.1111 | 6607450840302.73 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `inputs/portfolio_weights.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 1:1 최적 후보: SHY (최종점수 0.6575, CVaR 개선률 9.09%, Sharpe 개선률 1.13%)
- 다자산 최적 조합: SHY + IAU (최종점수 0.7049, CVaR 개선률 8.75%, Sharpe 개선률 4.82%)

## 단일 종목 질의 분석 요약
- 기준 자산: 005930.KS 100%
- 1:1 최적 후보: BTC-USD (예산 10.0%, 최종점수 0.7083)
- 다자산 최적 조합: BTC-USD + SHY (예산 10.0%, 최종점수 0.6330)

## 산출 파일
- `outputs/raw/raw_market_daily_20260507.csv`
- `outputs/raw/raw_fx_daily_20260507.csv`
- `outputs/raw/raw_benchmark_daily_20260507.csv`
- `outputs/reports/dq_result_latest-20260507-scenario.csv`
- `outputs/processed/features_summary_latest-20260507-scenario.csv`
- `outputs/reports/metric_validation_latest-20260507-scenario.csv`
- `outputs/reports/hes_components_latest-20260507-scenario.csv`
- `outputs/processed/asset_risk_sensitivity_latest-20260507-scenario.csv`
- `outputs/reports/asset_sensitivity_summary_latest-20260507-scenario.md`
- `outputs/processed/asset_scenario_sensitivity_latest-20260507-scenario.csv`
- `outputs/reports/asset_scenario_sensitivity_summary_latest-20260507-scenario.md`
- `outputs/reports/portfolio_1to1_hedge_latest-20260507-scenario.csv`
- `outputs/reports/portfolio_multi_hedge_latest-20260507-scenario.csv`
- `outputs/reports/portfolio_compare_latest-20260507-scenario.csv`
- `outputs/reports/single_asset_hedge_1to1_latest-20260507-scenario.csv`
- `outputs/reports/single_asset_hedge_multi_latest-20260507-scenario.csv`
- `outputs/reports/single_asset_compare_latest-20260507-scenario.csv`
