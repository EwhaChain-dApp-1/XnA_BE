# XnA (XRPL Q&A Platform)

블록체인 기반 지식 공유 Q&A 플랫폼입니다.
기존 지식인 서비스의 ‘내공’ 시스템처럼 XRP 보상 구조를 적용하여 질문자가 보상금을 걸고 답변자가 채택될 경우 이를 지급받는 구조입니다.

## 주요 기능

- Xaman Wallet 로그인 : XRPL 지갑(Xaman)을 통한 안전한 계정 연동

- 질문 등록 : 제목, 본문, 해시태그, 보상 XRP 입력

- 조건부 에스크로(Conditional Escrow) : 질문 등록 시 보상 XRP를 플랫폼 지갑으로 전달되고 플랫폼에서 에스크로 생성

- 답변 작성 : 질문에 자유롭게 답변 작성 가능

- 답변 채택 : 질문자가 답변을 채택하면, 에스크로가 해제되어 보상이 답변자에게 전달됨

## 기술 스택

- Frontend: Next.js (템플릿 사용)

- Backend: FastAPI, PostgreSQL

- Blockchain: XRPL (Escrow, Payment)

- Wallet Integration: Xaman SDK

## XRPL Korea Ambassador 활동
https://x.com/xrplkorea/status/1950842011894100108
