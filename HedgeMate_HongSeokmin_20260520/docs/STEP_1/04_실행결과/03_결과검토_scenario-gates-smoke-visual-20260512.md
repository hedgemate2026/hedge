# HedgeMate 실행 결과 검토 (2026-05-12)

## 1) 실행 성공 여부
- 파이프라인 실행: **성공**
- 대상 유니버스: 70개 티커
- 수집 성공: 70/70
- 위기구간(stress) 탐지: 66일
- 위기구간 벤치마크: SPY + ^KS200
- 기준통화: KRW

## 2) 핵심 점검
- FX 환산: PASS (USD 자산 KRW 기준 수익률 계산)
- Sharpe proxy: PASS (연 3.0% 무위험수익률 가정)
- DQ 결과 반영: PASS (`FAIL` 제외 / `WARN` 허용)
- 추천 로직: PASS (Gate + Final Score 구조)
- 단일 종목 질의 모드: PASS (`TSLA` 분석 가능)

## 3) 품질 검토
- DQ 결과: PASS 5 / WARN 65 / FAIL 0
- 지표 검증셋: PASS 7 / FAIL 0
- 포트폴리오 추천 결과 없음: Gate 통과 후보가 없어 참고안을 표시합니다. 리스크 관리가 어렵습니다.
- 단일 종목 추천 결과 없음: Gate 통과 후보가 없어 참고안을 표시합니다. 리스크 관리가 어렵습니다.

## 4) 참조 산출물
- `docs/STEP_1/04_실행결과/01_실행결과_scenario-gates-smoke-visual-20260512.md`
- `docs/STEP_1/04_실행결과/02_분석리포트_초안_scenario-gates-smoke-visual-20260512.md`
- `outputs/raw/raw_benchmark_daily_20260507.csv`
- `outputs/reports/dq_result_scenario-gates-smoke-visual-20260512.csv`
- `outputs/processed/features_summary_scenario-gates-smoke-visual-20260512.csv`
- `outputs/reports/hes_components_scenario-gates-smoke-visual-20260512.csv`
- `outputs/processed/asset_risk_sensitivity_scenario-gates-smoke-visual-20260512.csv`
- `outputs/reports/asset_sensitivity_summary_scenario-gates-smoke-visual-20260512.md`
- `outputs/processed/asset_scenario_sensitivity_scenario-gates-smoke-visual-20260512.csv`
- `outputs/reports/asset_scenario_sensitivity_summary_scenario-gates-smoke-visual-20260512.md`
- `outputs/reports/asset_scenario_sensitivity_visual_scenario-gates-smoke-visual-20260512.html`
- `outputs/reports/portfolio_1to1_hedge_scenario-gates-smoke-visual-20260512.csv`
- `outputs/reports/portfolio_multi_hedge_scenario-gates-smoke-visual-20260512.csv`
- `outputs/reports/portfolio_compare_scenario-gates-smoke-visual-20260512.csv`
- `outputs/reports/single_asset_hedge_1to1_scenario-gates-smoke-visual-20260512.csv`
- `outputs/reports/single_asset_hedge_multi_scenario-gates-smoke-visual-20260512.csv`
- `outputs/reports/single_asset_compare_scenario-gates-smoke-visual-20260512.csv`
