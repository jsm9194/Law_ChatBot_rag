import streamlit as st
from backend.tools.query_qdrant import ask  # 우리가 수정한 ask 함수 import

# --------------------------
# 페이지 기본 설정
st.set_page_config(page_title="⚖️ 시설관리 법령 챗봇", page_icon="🤖")

st.title("⚖️ 시설관리 법령 챗봇")
st.markdown("법령과 판례를 참고한 답변을 제공합니다. (참고용)")

# --------------------------
# 세션 상태에 대화 기록 저장
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --------------------------
# 사용자 입력
if user_input := st.chat_input("질문을 입력하세요..."):
    # 사용자 메시지 기록
    st.session_state.messages.append({"role": "user", "content": user_input})

     # LLM 컨텍스트로 넘길 이전 대화 정리
    conversation_context = "\n".join(
        [f"{m['role']}: {m['content']}" for m in st.session_state.messages]
    )
    answer, sources = ask(user_input, history=conversation_context)
    st.session_state.messages.append({"role": "assistant", "content": answer})

    with st.chat_message("user"):
        st.markdown(user_input)

    # 챗봇 답변
    with st.chat_message("assistant"):
        with st.spinner("법령 검색 중..."):
            answer, sources = ask(user_input)
            st.markdown(answer)

            # ✅ 출처 표시
            if sources:
                st.markdown("**출처:**")
                for src in sources:
                    # src가 "법령명 제12조 (http://...)" 형식이라고 가정
                    if "(" in src and src.endswith(")"):
                        # "법령명 제12조", "http://..." 분리
                        text, link = src.rsplit("(", 1)
                        link = link[:-1]  # 마지막 ")" 제거
                        st.markdown(f"- [{text.strip()}]({link})")  # 🔗 마크다운 링크 처리
                    else:
                        st.markdown(f"- {src}")

    # 답변 기록 (sources는 저장하지 않고 answer만 저장)
    st.session_state.messages.append({"role": "assistant", "content": answer})
