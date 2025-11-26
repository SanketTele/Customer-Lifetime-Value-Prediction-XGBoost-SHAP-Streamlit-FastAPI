# streamlit_app/app.py
import streamlit as st
import requests
import pandas as pd
import json
import io
import matplotlib.pyplot as plt
from typing import List, Dict

st.set_page_config(page_title="CLTV Predictor", layout="wide")

# ========== Configuration ==========
# The app looks for STREAMLIT_API_URL in Streamlit secrets first, then env var, then fallback
DEFAULT_API_URL = "https://cltv-backend-shap.onrender.com"
API_URL = st.secrets.get("STREAMLIT_API_URL", None) or DEFAULT_API_URL

st.title("Customer Lifetime Value (CLTV) — Demo")
st.markdown(
    "Enter a single customer (manual) or upload a CSV (batch) with features to get LTV predictions "
    "and explanations (top-3 feature impacts)."
)

# ========== Helper functions ==========
def call_predict_api(payload: dict, api_url: str = API_URL, timeout: int = 120) -> List[Dict]:
    url = api_url.rstrip("/") + "/predict"
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        st.error(f"HTTP error: {e} - {e.response.text if e.response is not None else ''}")
        return []
    except Exception as e:
        st.error(f"Request failed: {e}")
        return []

def single_payload_from_inputs(customer_id: str, inputs: dict) -> dict:
    cust = {"customer_id": customer_id}
    cust.update(inputs)
    return {"customers": [cust], "return_explanation": True}

def dataframe_to_payload(df: pd.DataFrame) -> dict:
    # ensure columns are lowercased / expected names
    customers = []
    for _, row in df.iterrows():
        d = row.to_dict()
        # ensure customer_id exists
        if "customer_id" not in d:
            d["customer_id"] = str(row.name)
        customers.append(d)
    return {"customers": customers, "return_explanation": True}

def show_explanation_bar(explanation: List[Dict], title: str = "Top features"):
    if not explanation:
        st.write("No explanation available.")
        return
    feats = [x["feature"] for x in explanation]
    impacts = [x["impact"] for x in explanation]
    # normalize display order descending impacts
    y_pos = range(len(feats))
    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.barh(y_pos, impacts[::-1])
    ax.set_yticks(y_pos)
    ax.set_yticklabels(feats[::-1])
    ax.set_xlabel("Impact on predicted LTV (positive increases LTV)")
    ax.set_title(title)
    st.pyplot(fig)

# ========== Sidebar: API settings & sample payload ==========
with st.sidebar:
    st.header("Settings")
    st.text_input("API base URL", value=API_URL, key="api_url_input")
    st.write("If you want to store the API URL securely, set STREAMLIT_API_URL in Streamlit Secrets.")
    st.markdown("---")
    st.header("Try sample")
    if st.button("Use sample single customer"):
        # sample defaults match your test
        st.session_state["load_sample_single"] = True
    if st.button("Use sample CSV (2 customers)"):
        st.session_state["load_sample_csv"] = True

# replace API_URL with sidebar value if changed
API_URL = st.session_state.get("api_url_input", API_URL).strip() or API_URL

# ========== Main: Manual single customer input ==========
st.subheader("1) Predict for a single customer")

col1, col2 = st.columns([1, 2])

with col1:
    cust_id = st.text_input("Customer ID", value="C101")
    frequency = st.number_input("frequency", value=4.0, step=1.0)
    total_spend = st.number_input("total_spend", value=200.0, step=1.0)
    aov = st.number_input("aov", value=50.0, step=1.0)
    recency_days = st.number_input("recency_days", value=20.0, step=1.0)
    T_days = st.number_input("T_days", value=300.0, step=1.0)

with col2:
    avg_interpurchase_days = st.number_input("avg_interpurchase_days", value=100.0, step=1.0)
    active_months = st.number_input("active_months", value=3.0, step=1.0)
    purchase_days_std = st.number_input("purchase_days_std", value=12.0, step=1.0)
    category_diversity = st.number_input("category_diversity", value=2.0, step=1.0)
    avg_order_value = st.number_input("avg_order_value", value=50.0, step=1.0)
    unique_days = st.number_input("unique_days", value=4.0, step=1.0)

if st.button("Predict single customer"):
    inputs = {
        "frequency": float(frequency),
        "total_spend": float(total_spend),
        "aov": float(aov),
        "recency_days": float(recency_days),
        "T_days": float(T_days),
        "avg_interpurchase_days": float(avg_interpurchase_days),
        "active_months": float(active_months),
        "purchase_days_std": float(purchase_days_std),
        "category_diversity": float(category_diversity),
        "avg_order_value": float(avg_order_value),
        "unique_days": float(unique_days),
    }
    payload = single_payload_from_inputs(cust_id, inputs)
    st.info("Calling API...")
    results = call_predict_api(payload, api_url=API_URL)
    if results:
        r = results[0]
        st.metric("Predicted LTV", f"{r['predicted_LTV']:.2f}")
        st.write("Segment:", r.get("segment"))
        st.markdown("**Top features (impact)**")
        show_explanation_bar(r.get("explanation", []))

# ========== CSV Batch Upload ==========
st.subheader("2) Batch: Upload CSV (columns must match feature names)")

uploaded = st.file_uploader("Upload CSV with columns: customer_id, frequency, total_spend, aov, recency_days, T_days, avg_interpurchase_days, active_months, purchase_days_std, category_diversity, avg_order_value, unique_days", type=["csv"])
if st.button("Predict from uploaded CSV") and uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
        st.write("Preview:", df.head())
        payload = dataframe_to_payload(df)
        st.info(f"Calling API for {len(payload['customers'])} customers...")
        results = call_predict_api(payload, api_url=API_URL)
        if results:
            out_df = pd.DataFrame(results)
            # flatten explanation into string
            out_df["top_features"] = out_df["explanation"].apply(lambda x: "; ".join([f'{d["feature"]}:{d["impact"]:.2f}' for d in x]) if x else "")
            st.write("Results preview:", out_df.head())
            csv = out_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download predictions CSV", data=csv, file_name="predictions_with_explanations.csv")
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")

# ========== Load sample buttons ==========
if st.session_state.get("load_sample_single", False):
    st.session_state["load_sample_single"] = False
    # populate sample values (same as your test payload)
    st.experimental_rerun()

if st.session_state.get("load_sample_csv", False):
    st.session_state["load_sample_csv"] = False
    # show example CSV content for download
    sample = pd.DataFrame([
        {"customer_id":"C101","frequency":4,"total_spend":200,"aov":50,"recency_days":20,"T_days":300,"avg_interpurchase_days":100,"active_months":3,"purchase_days_std":12,"category_diversity":2,"avg_order_value":50,"unique_days":4},
        {"customer_id":"C102","frequency":1,"total_spend":20,"aov":20,"recency_days":400,"T_days":400,"avg_interpurchase_days":400,"active_months":1,"purchase_days_std":5,"category_diversity":1,"avg_order_value":20,"unique_days":1},
    ])
    csv = sample.to_csv(index=False).encode("utf-8")
    st.download_button("Download sample CSV", data=csv, file_name="sample_customers.csv")
    st.experimental_rerun()
