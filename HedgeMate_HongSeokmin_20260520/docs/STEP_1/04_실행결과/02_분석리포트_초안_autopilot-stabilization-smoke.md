# HedgeMate 분석 리포트 초안

## 0. 리포트 메타
- 작성일: 2026-05-13
- 작성자: 자동 파이프라인
- 데이터 버전: 20260512
- 분석 기간: 최근 5년 목표, 데이터 부족 시 가용 구간 기준 계산 허용
- 데이터 주기: 일봉
- 기준통화: KRW
- 위기구간 정의: SPY + ^KS200 20거래일 수익률 <= -8%

- 현재 장세 요약: 현재 장세: 우호적 위험선호장(STRONG, us_global, score=72.62223) / 물가·에너지 재상승장(WATCH, us_global, score=51.480108) / 장기금리 부담장(WATCH, us_global, score=47.529611)
## 1. 데이터 품질 요약
- 수집 성공: 70/70
- DQ 판정(캘린더 기준): PASS 69, WARN 1, FAIL 0

## 2. 리스크 상위(KRW MDD 기준)
- USO: MDD_1y_krw=-0.1814, CVaR_95_1y_krw=-0.0602
- IAU: MDD_1y_krw=-0.1532, CVaR_95_1y_krw=-0.0409
- GLD: MDD_1y_krw=-0.1531, CVaR_95_1y_krw=-0.0412
- XLE: MDD_1y_krw=-0.1425, CVaR_95_1y_krw=-0.0338
- XLV: MDD_1y_krw=-0.1038, CVaR_95_1y_krw=-0.0243

## 3. 헷징 후보 Top10
- 시나리오 벡터: `..\scenario_research\outputs\scenario_vectors\current_scenario_vector_latest-20260512-refresh.csv`
1. USO (commodity_energy) - HES=0.5706 [Corr=1.000, CVaR=0.000, Stress=1.000, Sharpe=0.972, LiqPenalty=0.168]
2. XLE (commodity_energy) - HES=0.4101 [Corr=0.613, CVaR=0.570, Stress=0.303, Sharpe=0.727, LiqPenalty=0.368]
3. GLD (gold) - HES=0.4042 [Corr=0.298, CVaR=0.411, Stress=0.697, Sharpe=0.584, LiqPenalty=0.000]
4. LQD (bond) - HES=0.3625 [Corr=0.000, CVaR=0.961, Stress=0.550, Sharpe=0.200, LiqPenalty=0.118]
5. DBC (commodity_energy) - HES=0.3546 [Corr=0.771, CVaR=0.647, Stress=0.000, Sharpe=1.000, LiqPenalty=1.000]
6. XLU (defensive) - HES=0.3142 [Corr=0.282, CVaR=0.745, Stress=0.630, Sharpe=0.318, LiqPenalty=0.776]
7. SHY (bond) - HES=0.2987 [Corr=0.125, CVaR=1.000, Stress=0.723, Sharpe=0.081, LiqPenalty=0.927]
8. XLV (defensive) - HES=0.2966 [Corr=0.033, CVaR=0.775, Stress=0.870, Sharpe=0.101, LiqPenalty=0.631]
9. IEF (bond) - HES=0.2860 [Corr=0.066, CVaR=0.981, Stress=0.657, Sharpe=0.102, LiqPenalty=0.816]
10. IAU (gold) - HES=0.2831 [Corr=0.296, CVaR=0.418, Stress=0.697, Sharpe=0.592, LiqPenalty=0.824]

## 4. 포트폴리오 개선 효과 (KRW 기준)
| 시나리오 | 변동성 | MDD | CVaR(95%) | 연환산수익률 | Sharpe | 변동성 개선률(%) | MDD 개선률(%) | CVaR 개선률(%) | Sharpe 개선률(%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 기존 포트폴리오 | 0.202756 | -0.190808 | -0.025169 | 0.330080 | 1.480002 | 0.00 | 0.00 | 0.00 | 0.00 |
| 제안(1:1) - GLD | 0.170957 | -0.157043 | -0.021519 | 0.321519 | 1.705218 | 15.68 | 17.70 | 14.50 | 15.22 |
| 제안(다자산) - SHY + IAU | 0.152452 | -0.132548 | -0.019332 | 0.290813 | 1.710793 | 24.81 | 30.53 | 23.19 | 15.59 |

## 6. 다음 액션
- FX carry-forward 허용 범위 및 예외 처리 검토
- 단일 종목 질의 결과를 API/UI 입력 흐름에 연결
- 무위험수익률 실데이터 연결로 Sharpe proxy 고도화
