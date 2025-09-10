import streamlit as st
from query_qdrant import ask

st.set_page_config(page_title="⚖️ 시설관리 법령 챗봇", page_icon="🤖")

st.title("⚖️ 시설관리 법령 챗봇")
st.markdown("법령과 판례를 참고한 답변을 제공합니다. (참고용)")

# 세션 상태에 대화 기록 저장
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 사용자 입력
if user_input := st.chat_input("질문을 입력하세요..."):
    # 사용자 메시지 기록
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 챗봇 답변
    with st.chat_message("assistant"):
        with st.spinner("검색 중..."):
            answer, sources = ask(user_input)
            st.markdown(answer)

             # ✅ 출처 표시
            st.markdown("**출처:**")
            for src in sources:
                st.markdown(f"- {src}")

    # 답변 기록
    st.session_state.messages.append({"role": "assistant", "content": answer})
