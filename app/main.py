import streamlit as st

st.set_page_config(
    page_title="Welfare Indonesia",
    page_icon="📊",
    layout="wide"
)

st.title("Memetakan Perbedaan Kesejahteraan Indonesia")
st.write("Prototype Visualisasi Data dan Informasi")

mapbox_token = st.secrets["MAPBOX_TOKEN"]

st.success("Mapbox token berhasil dibaca.")
