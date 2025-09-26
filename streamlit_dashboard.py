import streamlit as st
import pandas as pd
import numpy as np
import datetime
import io
import plotly.express as px

# ------------------ MOCK 数据生成 ------------------
np.random.seed(42)
platforms = ['美团', '京东', '字节']
risk_modes = ['自营', '联合运营-乐信', '联合运营-360']
approve_statuses = ['通过', '拒绝', '卡单']
exception_types = ['无', '分发失败', '审批异常']

# 生成近30天分钟级数据
dates = pd.date_range(datetime.datetime.now() - datetime.timedelta(days=30), periods=30*24*60, freq='T')
dates = pd.date_range(datetime.datetime.now() - datetime.timedelta(days=7), periods=7*24*60, freq='T')
mock_data = []
for dt in dates:
    platform = np.random.choice(platforms)
    risk_mode = np.random.choice(risk_modes)
    loan_id = f"L{np.random.randint(100000,999999)}"
    dispatch_amount = np.random.randint(1000, 10000)
    approve_amount = dispatch_amount if np.random.rand() < 0.7 else 0
    approve_status = np.random.choice(approve_statuses, p=[0.7,0.25,0.05])
    approve_time = dt + datetime.timedelta(minutes=np.random.randint(1,10)) if approve_status != '卡单' else None
    is_degraded = int(np.random.rand() < 0.08)
    degrade_reason = '超时' if is_degraded else ''
    exception_type = np.random.choice(exception_types, p=[0.94,0.03,0.03])
    mock_data.append({
        'platform': platform,
        'loan_id': loan_id,
        'dispatch_time': dt,
        'risk_mode': risk_mode,
        'dispatch_amount': dispatch_amount,
        'approve_amount': approve_amount,
        'approve_status': approve_status,
        'approve_time': approve_time,
        'is_degraded': is_degraded,
        'degrade_reason': degrade_reason,
        'exception_type': exception_type,
    })
df = pd.DataFrame(mock_data)

# ------------------ Streamlit UI ------------------
st.set_page_config(page_title="流量分发监控看板", layout="wide")
st.title("流量分发监控看板")

# 筛选区
with st.sidebar:
    st.header("筛选条件")
    start_date = st.date_input("开始日期", value=df['dispatch_time'].min().date())
    end_date = st.date_input("结束日期", value=df['dispatch_time'].max().date())
    platform_sel = st.multiselect("平台", platforms, default=platforms)
    risk_mode_sel = st.multiselect("风控模式", risk_modes, default=risk_modes)
    export_btn = st.button("导出当前数据为Excel")

# 数据筛选
df_filtered = df[(df['dispatch_time'].dt.date >= start_date) & (df['dispatch_time'].dt.date <= end_date)]
df_filtered = df_filtered[df_filtered['platform'].isin(platform_sel)]
df_filtered = df_filtered[df_filtered['risk_mode'].isin(risk_mode_sel)]

# ------------------ 指标卡 ------------------
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
col1.metric("分发笔数", len(df_filtered))
col2.metric("分发金额总量", int(df_filtered['dispatch_amount'].sum()))
col3.metric("审批通过金额", int(df_filtered[df_filtered['approve_status']=='通过']['approve_amount'].sum()))
col4.metric("批核效率(通过率)", f"{(df_filtered['approve_status']=='通过').mean()*100:.2f}%")
col5.metric("卡单数量", int((df_filtered['approve_status']=='卡单').sum()))
col6.metric("降级数量", int(df_filtered['is_degraded'].sum()))
col7.metric("异常数量", int((df_filtered['exception_type']!='无').sum()))

# ------------------ 趋势图 ------------------
st.subheader("指标趋势图")
trend_metric = st.selectbox("选择趋势指标", ["分发笔数", "分发金额总量", "审批通过金额", "批核效率", "卡单数量", "降级数量", "异常数量"])
trend_df = df_filtered.copy()
trend_df['minute'] = trend_df['dispatch_time'].dt.floor('T')
grouped = trend_df.groupby('minute')
if trend_metric == "分发笔数":
    y = grouped.size()
elif trend_metric == "分发金额总量":
    y = grouped['dispatch_amount'].sum()
elif trend_metric == "审批通过金额":
    y = grouped[trend_df['approve_status']=='通过']['approve_amount'].sum()
elif trend_metric == "批核效率":
    y = grouped.apply(lambda x: (x['approve_status']=='通过').mean()*100)
elif trend_metric == "卡单数量":
    y = grouped.apply(lambda x: (x['approve_status']=='卡单').sum())
elif trend_metric == "降级数量":
    y = grouped['is_degraded'].sum()
elif trend_metric == "异常数量":
    y = grouped.apply(lambda x: (x['exception_type']!='无').sum())
fig = px.line(x=y.index, y=y.values, labels={'x':'时间','y':trend_metric}, title=trend_metric)
st.plotly_chart(fig, use_container_width=True)

# ------------------ 明细表格 ------------------
st.subheader("流量分发明细表")
st.dataframe(df_filtered.head(100), use_container_width=True)

# ------------------ 异常分布 ------------------
st.subheader("异常分布")
ex_df = df_filtered[df_filtered['exception_type']!='无']
ex_count = ex_df['exception_type'].value_counts()
fig_ex = px.pie(names=ex_count.index, values=ex_count.values, title="异常类型分布")
st.plotly_chart(fig_ex, use_container_width=True)
st.dataframe(ex_df.head(50), use_container_width=True)

# ------------------ 降级流转路径（简化） ------------------
st.subheader("降级流转路径")
degrade_df = df_filtered[df_filtered['is_degraded']==1]
if not degrade_df.empty:
    degrade_count = degrade_df.groupby(['risk_mode','degrade_reason']).size().reset_index(name='数量')
    fig_deg = px.sunburst(degrade_count, path=['risk_mode','degrade_reason'], values='数量', title="降级流转路径")
    st.plotly_chart(fig_deg, use_container_width=True)
else:
    st.info("当前筛选条件下无降级数据")

# ------------------ Excel 导出 ------------------
if export_btn:
    output = io.BytesIO()
    df_filtered.to_excel(output, index=False)
    st.download_button(label="下载Excel", data=output.getvalue(), file_name="流量分发明细.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
