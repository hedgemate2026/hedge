# HedgeMate 분석 리포트 초안

## 0. 리포트 메타
- 작성일: 2026-05-18
- 작성자: 자동 파이프라인
- 데이터 버전: 20260518
- 분석 기간: 최근 5년 목표, 데이터 부족 시 가용 구간 기준 계산 허용
- 데이터 주기: 일봉
- 기준통화: KRW
- 위기구간 정의: SPY + ^KS200 20거래일 수익률 <= -8%

- 현재 장세 요약: 현재 장세: 장기금리 부담장(STRESS, us_global, score=77.142012) / 물가·에너지 재상승장(ACTIVE, us_global, score=72.756862) / 달러강세/원화약세장(PROVISIONAL, fx_krw, score=60.402968)
## 1. 데이터 품질 요약
- 수집 성공: 70/70
- DQ 판정(캘린더 기준): PASS 69, WARN 1, FAIL 0

## 2. 리스크 상위(KRW MDD 기준)
- USO: MDD_1y_krw=-0.1814, CVaR_95_1y_krw=-0.0602
- GLD: MDD_1y_krw=-0.1531, CVaR_95_1y_krw=-0.0411
- XLE: MDD_1y_krw=-0.1425, CVaR_95_1y_krw=-0.0338
- XLV: MDD_1y_krw=-0.1038, CVaR_95_1y_krw=-0.0223
- DBC: MDD_1y_krw=-0.0803, CVaR_95_1y_krw=-0.0302

## 3. 헷징 후보 Top10
- 시나리오 벡터: `scenario_research\outputs\scenario_vectors\current_scenario_vector_final-refresh-20260518b.csv`
1. USO (commodity_energy) - HES=0.4941 [Corr=1.000, CVaR=0.000, Stress=1.000, Sharpe=0.437, LiqPenalty=0.143]
2. XLE (commodity_energy) - HES=0.4045 [Corr=0.612, CVaR=0.570, Stress=0.584, Sharpe=0.314, LiqPenalty=0.367]
3. LQD (bond) - HES=0.3865 [Corr=0.000, CVaR=0.965, Stress=0.732, Sharpe=0.093, LiqPenalty=0.101]
4. GLD (gold) - HES=0.3728 [Corr=0.273, CVaR=0.412, Stress=0.819, Sharpe=0.252, LiqPenalty=0.000]
5. DBC (commodity_energy) - HES=0.3411 [Corr=0.748, CVaR=0.647, Stress=0.404, Sharpe=0.409, LiqPenalty=1.000]
6. XLV (defensive) - HES=0.3236 [Corr=0.043, CVaR=0.819, Stress=0.922, Sharpe=0.118, LiqPenalty=0.626]
7. SHY (bond) - HES=0.3180 [Corr=0.127, CVaR=1.000, Stress=0.835, Sharpe=0.054, LiqPenalty=0.925]
8. TLT (bond) - HES=0.3157 [Corr=0.068, CVaR=0.909, Stress=0.663, Sharpe=0.000, LiqPenalty=0.408]
9. IEF (bond) - HES=0.3061 [Corr=0.059, CVaR=0.982, Stress=0.795, Sharpe=0.056, LiqPenalty=0.813]
10. XLU (defensive) - HES=0.2961 [Corr=0.223, CVaR=0.735, Stress=0.780, Sharpe=0.113, LiqPenalty=0.775]

## 4. 포트폴리오 개선 효과 (KRW 기준)
| 시나리오 | 변동성 | MDD | CVaR(95%) | 연환산수익률 | Sharpe | 변동성 개선률(%) | MDD 개선률(%) | CVaR 개선률(%) | Sharpe 개선률(%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 기존 포트폴리오 | 0.243308 | -0.406246 | -0.033875 | 0.352369 | 1.324941 | 0.00 | 0.00 | 0.00 | 0.00 |
| 제안(1:1) - GLD | 0.203485 | -0.334049 | -0.027794 | 0.338723 | 1.517181 | 16.37 | 17.77 | 17.95 | 14.51 |
| 제안(다자산) - TLT + GLD | 0.221980 | -0.374582 | -0.030627 | 0.340806 | 1.400157 | 8.77 | 7.79 | 9.59 | 5.68 |

## 6. 다음 액션
- FX carry-forward 허용 범위 및 예외 처리 검토
- 단일 종목 질의 결과를 API/UI 입력 흐름에 연결
- 무위험수익률 실데이터 연결로 Sharpe proxy 고도화
