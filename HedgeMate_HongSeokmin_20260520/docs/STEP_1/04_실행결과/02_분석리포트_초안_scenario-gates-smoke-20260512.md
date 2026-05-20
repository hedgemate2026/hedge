# HedgeMate 분석 리포트 초안

## 0. 리포트 메타
- 작성일: 2026-05-12
- 작성자: 자동 파이프라인
- 데이터 버전: 20260507
- 분석 기간: 최근 5년 목표, 데이터 부족 시 가용 구간 기준 계산 허용
- 데이터 주기: 일봉
- 기준통화: KRW
- 위기구간 정의: SPY + ^KS200 20거래일 수익률 <= -8%

- 현재 장세 요약: 현재 장세: 우호적 위험선호장(STRONG, us_global, score=75.158538) / 물가·에너지 재상승장(WATCH, us_global, score=48.464917)
## 1. 데이터 품질 요약
- 수집 성공: 70/70
- DQ 판정(캘린더 기준): PASS 5, WARN 65, FAIL 0

## 2. 리스크 상위(KRW MDD 기준)
- BTC-USD: MDD_1y_krw=-0.4795, CVaR_95_1y_krw=-0.0554
- 068270.KS: MDD_1y_krw=-0.2423, CVaR_95_1y_krw=-0.0486
- 032830.KS: MDD_1y_krw=-0.1972, CVaR_95_1y_krw=-0.0525
- 017670.KS: MDD_1y_krw=-0.1873, CVaR_95_1y_krw=-0.0506
- USO: MDD_1y_krw=-0.1814, CVaR_95_1y_krw=-0.0588

## 3. 헷징 후보 Top10
- 시나리오 벡터: `../scenario_research/outputs/scenario_vectors/current_scenario_vector_latest-20260507.csv`
1. DBC (commodity_energy) - HES=0.3467 [Corr=0.742, CVaR=0.786, Stress=0.362, Sharpe=0.283, LiqPenalty=1.000]
2. BTC-USD (crypto) - HES=0.3280 [Corr=0.271, CVaR=0.420, Stress=0.761, Sharpe=0.020, LiqPenalty=0.000]
3. 055550.KS (kr_stock) - HES=0.3237 [Corr=0.946, CVaR=0.604, Stress=0.194, Sharpe=0.316, LiqPenalty=1.000]
4. XOM (us_stock) - HES=0.3211 [Corr=0.725, CVaR=0.677, Stress=0.427, Sharpe=0.234, LiqPenalty=1.000]
5. 017670.KS (kr_stock) - HES=0.3171 [Corr=0.949, CVaR=0.487, Stress=0.395, Sharpe=0.195, LiqPenalty=1.000]
6. USO (commodity_energy) - HES=0.3145 [Corr=0.914, CVaR=0.374, Stress=0.501, Sharpe=0.281, LiqPenalty=1.000]
7. XLE (commodity_energy) - HES=0.3134 [Corr=0.647, CVaR=0.737, Stress=0.404, Sharpe=0.244, LiqPenalty=1.000]
8. 068270.KS (kr_stock) - HES=0.3117 [Corr=0.973, CVaR=0.514, Stress=0.346, Sharpe=0.137, LiqPenalty=1.000]
9. 032830.KS (kr_stock) - HES=0.3080 [Corr=0.881, CVaR=0.460, Stress=0.235, Sharpe=0.506, LiqPenalty=1.000]
10. JNJ (defensive) - HES=0.3034 [Corr=0.399, CVaR=0.857, Stress=0.477, Sharpe=0.293, LiqPenalty=1.000]

## 4. 포트폴리오 개선 효과 (KRW 기준)
| 시나리오 | 변동성 | MDD | CVaR(95%) | 연환산수익률 | Sharpe | 변동성 개선률(%) | MDD 개선률(%) | CVaR 개선률(%) | Sharpe 개선률(%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 기존 포트폴리오 | 0.202856 | -0.190808 | -0.025169 | 0.325342 | 1.455925 | 0.00 | 0.00 | 0.00 | 0.00 |
| 참고안(다자산) - TLT + GLD | 0.185157 | -0.174848 | -0.023003 | 0.317103 | 1.550595 | 8.72 | 8.36 | 8.61 | 6.50 |

- 추천 결과 없음: Gate 통과 후보가 없어 참고안을 표시합니다. 리스크 관리가 어렵습니다.

## 5. 단일 종목 질의 결과 (TSLA)
- 기준(TSLA 100%): CVaR=-0.079913, MDD=-0.716030, Sharpe=0.255869
- 참고안(1:1) - GLD: CVaR=-0.072102, MDD=-0.667032, Sharpe=0.339635
- 추천 결과 없음: Gate 통과 후보가 없어 참고안을 표시합니다. 리스크 관리가 어렵습니다.

## 6. 다음 액션
- FX carry-forward 허용 범위 및 예외 처리 검토
- 단일 종목 질의 결과를 API/UI 입력 흐름에 연결
- 무위험수익률 실데이터 연결로 Sharpe proxy 고도화
