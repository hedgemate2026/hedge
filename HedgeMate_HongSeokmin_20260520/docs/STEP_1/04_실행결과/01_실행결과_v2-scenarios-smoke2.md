# HedgeMate 데이터 파이프라인 실행 결과

- 실행일(UTC): 2026-05-13T11:28:09.193711+00:00
- 데이터 버전(data_version): 20260512
- 분석기간: 2021-05-04 ~ 2026-05-13
- 기준통화: KRW
- 대상 티커: 70개
- 수집 성공 티커: 70개
- 위기구간(stress) 일수: 66일
- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)
- 시나리오 벡터: `..\scenario_research\outputs\scenario_vectors\current_scenario_vector_v2-scenarios-smoke2.csv`
- 현재 장세 요약: 현재 장세: 우호적 위험선호장(STRONG, us_global, score=72.622232) / 물가·에너지 재상승장(WATCH, us_global, score=51.480108) / 장기금리 부담장(WATCH, us_global, score=47.529609)
- Active adverse scenario: 물가·에너지 재상승장, 장기금리 부담장, 한국 내수 금융스트레스장
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
| 1 | USO | commodity_energy | 0.5706 | 1.0000 | 0.0000 | 1.0000 | 0.9715 | 0.1676 | -0.3009 | -0.0602 | 2.5567 | 6136944437784.01 |
| 2 | XLE | commodity_energy | 0.4101 | 0.6128 | 0.5700 | 0.3025 | 0.7274 | 0.3683 | 0.1124 | -0.0338 | 1.9929 | 4674103261514.71 |
| 3 | GLD | gold | 0.4042 | 0.2980 | 0.4112 | 0.6966 | 0.5839 | 0.0000 | 0.4485 | -0.0412 | 1.6616 | 7358407140301.69 |
| 4 | LQD | bond | 0.3625 | 0.0000 | 0.9605 | 0.5501 | 0.1999 | 0.1177 | 0.7666 | -0.0157 | 0.7748 | 6500596546694.17 |
| 5 | DBC | commodity_energy | 0.3546 | 0.7711 | 0.6472 | 0.0000 | 1.0000 | 1.0000 | -0.0566 | -0.0302 | 2.6225 | 70718685088.67 |
| 6 | XLU | defensive | 0.3142 | 0.2823 | 0.7448 | 0.6300 | 0.3179 | 0.7755 | 0.4652 | -0.0257 | 1.0472 | 1706639447042.78 |
| 7 | SHY | bond | 0.2987 | 0.1248 | 1.0000 | 0.7227 | 0.0805 | 0.9273 | 0.6333 | -0.0139 | 0.4991 | 600734922824.17 |
| 8 | XLV | defensive | 0.2966 | 0.0331 | 0.7754 | 0.8698 | 0.1009 | 0.6307 | 0.7313 | -0.0243 | 0.5461 | 2762060794874.65 |
| 9 | IEF | bond | 0.2860 | 0.0663 | 0.9808 | 0.6568 | 0.1020 | 0.8161 | 0.6959 | -0.0148 | 0.5487 | 1410786519178.27 |
| 10 | IAU | gold | 0.2831 | 0.2964 | 0.4180 | 0.6967 | 0.5918 | 0.8238 | 0.4502 | -0.0409 | 1.6797 | 1355086119516.59 |

## 포트폴리오 입력 분석 요약
- 입력 파일: `inputs\portfolio_weights.csv`
- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)
- 추천상태 분포: FAIL_GATE 1, PASS_RECOMMEND 25, REFERENCE_ONLY 8
- 1:1 최적 후보: GLD (최종점수 0.6680, CVaR 개선률 8.18%, Sharpe 개선률 7.77%)
- 다자산 최적 조합: SHY + IAU (최종점수 0.6671, CVaR 개선률 8.48%, Sharpe 개선률 6.56%)

## 단일 종목 질의 분석 요약
- 기준 자산: TSLA 100%
- 추천상태 분포: PASS_RECOMMEND 35
- 1:1 최적 후보: GLD (예산 10.0%, 최종점수 0.6875)
- 다자산 최적 조합: GLD + SHY (예산 10.0%, 최종점수 0.6548)

## 산출 파일
- `outputs\raw\raw_market_daily_20260512.csv`
- `outputs\raw\raw_fx_daily_20260512.csv`
- `outputs\raw\raw_benchmark_daily_20260512.csv`
- `outputs\reports\dq_result_v2-scenarios-smoke2.csv`
- `outputs\processed\features_summary_v2-scenarios-smoke2.csv`
- `outputs\reports\metric_validation_v2-scenarios-smoke2.csv`
- `outputs\reports\hes_components_v2-scenarios-smoke2.csv`
- `outputs\processed\asset_risk_sensitivity_v2-scenarios-smoke2.csv`
- `outputs\reports\asset_sensitivity_summary_v2-scenarios-smoke2.md`
- `outputs\processed\asset_scenario_sensitivity_v2-scenarios-smoke2.csv`
- `outputs\reports\asset_scenario_sensitivity_summary_v2-scenarios-smoke2.md`
- `outputs\reports\asset_scenario_sensitivity_visual_v2-scenarios-smoke2.html`
- `outputs\reports\recommendation_status_qa_v2-scenarios-smoke2.md`
- `outputs\reports\portfolio_1to1_hedge_v2-scenarios-smoke2.csv`
- `outputs\reports\portfolio_multi_hedge_v2-scenarios-smoke2.csv`
- `outputs\reports\portfolio_compare_v2-scenarios-smoke2.csv`
- `outputs\reports\single_asset_hedge_1to1_v2-scenarios-smoke2.csv`
- `outputs\reports\single_asset_hedge_multi_v2-scenarios-smoke2.csv`
- `outputs\reports\single_asset_compare_v2-scenarios-smoke2.csv`
