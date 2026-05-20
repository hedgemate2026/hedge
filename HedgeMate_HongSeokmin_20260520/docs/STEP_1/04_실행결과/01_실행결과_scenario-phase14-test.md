# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-04-15T11:01:58.021645+00:00
- 데이터 버전(data_version): 20260311
- 분석기간: 2021-04-06 ~ 2026-04-15
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 62일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
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
| 1 | IAU | gold | 0.4152 | 0.8273 | 0.6683 | 0.2067 | 1.0000 | 1.0000 | 0.2453 | -0.0385 | 2.9356 | 2019363794163.39 |
| 2 | GLD | gold | 0.4129 | 0.8256 | 0.6644 | 0.2071 | 0.9934 | 1.0000 | 0.2463 | -0.0388 | 2.9109 | 11790667529426.02 |
| 3 | BTC-USD | crypto | 0.3325 | 0.1219 | 0.4082 | 1.0000 | 0.0000 | 0.0000 | 0.6575 | -0.0553 | -0.8195 | 5115244366438626304.00 |
| 4 | USO | commodity_energy | 0.3299 | 1.0000 | 0.4690 | 0.1605 | 0.5367 | 1.0000 | 0.1444 | -0.0514 | 1.1960 | 1970411033369.56 |
| 5 | DBC | commodity_energy | 0.3023 | 0.6699 | 0.7866 | 0.0000 | 0.5877 | 1.0000 | 0.3373 | -0.0309 | 1.3874 | 33038140663.33 |
| 6 | XLU | defensive | 0.2943 | 0.4173 | 0.8457 | 0.2209 | 0.5625 | 1.0000 | 0.4849 | -0.0271 | 1.2926 | 1652371122215.00 |
| 7 | XLP | defensive | 0.2627 | 0.4904 | 0.8651 | 0.1510 | 0.2906 | 1.0000 | 0.4422 | -0.0258 | 0.2717 | 2488623226120.12 |
| 8 | XLE | commodity_energy | 0.2528 | 0.6282 | 0.5773 | 0.1219 | 0.5135 | 1.0000 | 0.3617 | -0.0444 | 1.1086 | 3906806842509.89 |
| 9 | IEF | bond | 0.2331 | 0.1470 | 0.9925 | 0.2515 | 0.3195 | 1.0000 | 0.6428 | -0.0176 | 0.3802 | 1255579678910.79 |
| 10 | TLT | bond | 0.2159 | 0.2453 | 0.9358 | 0.1860 | 0.2231 | 1.0000 | 0.5854 | -0.0213 | 0.0181 | 4971757120341.56 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `inputs\portfolio_weights.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 1:1 최적 후보: SHY (최종점수 0.7532, CVaR 개선률 17.80%, Sharpe 개선률 1.00%)
- 다자산 최적 조합: IAU + SHY (최종점수 0.7728, CVaR 개선률 23.93%, Sharpe 개선률 13.87%)

## 산출 파일
- `outputs\raw\raw_market_daily_20260311.csv`
- `outputs\raw\raw_fx_daily_20260311.csv`
- `outputs\raw\raw_benchmark_daily_20260311.csv`
- `outputs\reports\dq_result_scenario-phase14-test.csv`
- `outputs\processed\features_summary_scenario-phase14-test.csv`
- `outputs\reports\metric_validation_scenario-phase14-test.csv`
- `outputs\reports\hes_components_scenario-phase14-test.csv`
- `outputs\processed\asset_risk_sensitivity_scenario-phase14-test.csv`
- `outputs\reports\asset_sensitivity_summary_scenario-phase14-test.md`
- `outputs\reports\portfolio_1to1_hedge_scenario-phase14-test.csv`
- `outputs\reports\portfolio_multi_hedge_scenario-phase14-test.csv`
- `outputs\reports\portfolio_compare_scenario-phase14-test.csv`
