# HedgeMate 분석 리포트 초안

## 0. 리포트 메타
- 작성일: 2026-04-15
- 작성자: 자동 파이프라인
- 데이터 버전: 20260415
- 분석 기간: 최근 5년 목표, 데이터 부족 시 가용 구간 기준 계산 허용
- 데이터 주기: 일봉
- 기준통화: KRW
- 위기구간 정의: SPY + ^KS200 20거래일 수익률 <= -8%

## 1. 데이터 품질 요약
- 수집 성공: 70/70
- DQ 판정(캘린더 기준): PASS 5, WARN 65, FAIL 0

## 2. 리스크 상위(KRW MDD 기준)
- BTC-USD: MDD_1y_krw=-0.4795, CVaR_95_1y_krw=-0.0554
- USO: MDD_1y_krw=-0.1600, CVaR_95_1y_krw=-0.0553
- IAU: MDD_1y_krw=-0.1532, CVaR_95_1y_krw=-0.0410
- GLD: MDD_1y_krw=-0.1531, CVaR_95_1y_krw=-0.0413
- XLE: MDD_1y_krw=-0.1243, CVaR_95_1y_krw=-0.0341

## 3. 헷징 후보 Top10
1. USO (commodity_energy) - HES=0.4210 [Corr=1.000, CVaR=0.405, Stress=0.350, Sharpe=1.000, LiqPenalty=1.000]
2. DBC (commodity_energy) - HES=0.3867 [Corr=0.753, CVaR=0.793, Stress=0.000, Sharpe=1.000, LiqPenalty=1.000]
3. XLE (commodity_energy) - HES=0.3467 [Corr=0.575, CVaR=0.731, Stress=0.106, Sharpe=0.993, LiqPenalty=1.000]
4. BTC-USD (crypto) - HES=0.3334 [Corr=0.131, CVaR=0.403, Stress=1.000, Sharpe=0.000, LiqPenalty=0.000]
5. IAU (gold) - HES=0.3034 [Corr=0.442, CVaR=0.625, Stress=0.244, Sharpe=0.920, LiqPenalty=1.000]
6. GLD (gold) - HES=0.3018 [Corr=0.443, CVaR=0.621, Stress=0.244, Sharpe=0.914, LiqPenalty=1.000]
7. XLU (defensive) - HES=0.2906 [Corr=0.264, CVaR=0.845, Stress=0.220, Sharpe=0.796, LiqPenalty=1.000]
8. SHY (bond) - HES=0.2348 [Corr=0.115, CVaR=1.000, Stress=0.253, Sharpe=0.370, LiqPenalty=1.000]
9. IEF (bond) - HES=0.2311 [Corr=0.096, CVaR=0.987, Stress=0.230, Sharpe=0.429, LiqPenalty=1.000]
10. TIP (bond) - HES=0.2253 [Corr=0.104, CVaR=0.987, Stress=0.177, Sharpe=0.448, LiqPenalty=1.000]

## 4. 포트폴리오 개선 효과 (KRW 기준)
| 시나리오 | 변동성 | MDD | CVaR(95%) | 연환산수익률 | Sharpe | 변동성 개선률(%) | MDD 개선률(%) | CVaR 개선률(%) | Sharpe 개선률(%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 기존 포트폴리오 | 0.202443 | -0.190808 | -0.025111 | 0.344463 | 1.553342 | 0.00 | 0.00 | 0.00 | 0.00 |
| 제안(1:1) - SHY | 0.183314 | -0.168327 | -0.022825 | 0.317195 | 1.566684 | 9.45 | 11.78 | 9.10 | 0.86 |
| 제안(다자산) - IAU + SHY | 0.184163 | -0.171196 | -0.022924 | 0.329249 | 1.624909 | 9.03 | 10.28 | 8.71 | 4.61 |

## 6. 다음 액션
- FX carry-forward 허용 범위 및 예외 처리 검토
- 단일 종목 질의 결과를 API/UI 입력 흐름에 연결
- 무위험수익률 실데이터 연결로 Sharpe proxy 고도화
