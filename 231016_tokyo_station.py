import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
import jaconv
from sklearn.preprocessing import MinMaxScaler
from streamlit_folium import st_folium
import numpy as np
import plotly.graph_objects as go

# 全角数字を半角数字に置き換える式を作成する
def convert_zenkaku(df, column):
    df[column] = df[column].apply(lambda x: jaconv.z2h(x, digit=True, ascii=False))
    return df

# 半角数字を漢数字に置き換える式を作成する
def convert_chome(df, column):
    # 指定した列の文字列を変換する
    df[column] = df[column].apply(lambda x: jaconv.z2h(x, digit=True, ascii=False))

    # 半角数字を漢数字に変換する辞書
    num_dict = {
        '0': '〇',
        '1': '一',
        '2': '二',
        '3': '三',
        '4': '四',
        '5': '五',
        '6': '六',
        '7': '七',
        '8': '八',
        '9': '九'
    }

    # 辞書を使用して半角数字を漢数字に変換する
    df[column] = df[column].replace(num_dict, regex=True)

    return df


# 各区のシェイプファイルを読み込む
chiyoda = gpd.read_file("r2ka13101.shp")
chuou = gpd.read_file("r2ka13102.shp")
minato = gpd.read_file("r2ka13103.shp")
shinjuku = gpd.read_file("r2ka13104.shp")
bunkyo = gpd.read_file("r2ka13105.shp")
taito = gpd.read_file("r2ka13106.shp")



# 各区のデータをtokyo_stationとして１つにまとめる
tokyo_station = pd.concat([chiyoda, chuou, minato, shinjuku, bunkyo, taito], ignore_index=True)
# 区と丁目をくっつけたarea_nameカラムを作成する
tokyo_station["area_name"] = tokyo_station["CITY_NAME"].str.cat(tokyo_station["S_NAME"], sep='')

# 犯罪スコアのデータを読み込む
_score = pd.read_csv("hanzai_rankmap.csv")
columns = ["市区町丁", "計"]
score = _score[columns]

# 犯罪スコアデータの住所で全角数字を漢数字に変換する
score_re = convert_zenkaku(score, "市区町丁")
score_re = convert_chome(score_re, '市区町丁')

# シェイプデータに各町の犯罪スコアを連結する
tokyo_station = tokyo_station.merge(score_re, left_on='area_name', right_on='市区町丁', how='left')

# scoreカラムに計のデータを書き込み
tokyo_station['score'] = tokyo_station['計']

# 不要なカラムを削除
tokyo_station = tokyo_station.drop(['市区町丁', '計'], axis=1)

# scoreを0-1の範囲に変換する（のちの色分け時に必要）
scaler = MinMaxScaler()
tokyo_station['score_re'] = scaler.fit_transform(tokyo_station[['score']])

# scoreを0-1の範囲に変換する：対数変換ver
# スコアの対数を取る
log_scores = np.log(tokyo_station['score'])

# MinMaxScalerオブジェクトを作成
scaler = MinMaxScaler()

# スコアを正規化
tokyo_station["normalized_score"] = scaler.fit_transform(log_scores.values.reshape(-1, 1))

# 対数変換ver
# tokyo_stationデータフレームをgeopandasのGeoDataFrameに変換
gdf_tokyo_station = gpd.GeoDataFrame(tokyo_station, geometry='geometry')

# 検索に使用する駅のデータを作成する
sta_name = ["東京駅","有楽町駅", "大手町駅", "二重橋前駅", "日比谷駅", "京橋駅", "銀座一丁目駅", "銀座駅", "日本橋駅", "宝町駅"]
sta_longitudes = [35.68125882,35.67457594,35.68484,35.68044,35.67495,35.676856,35.67432,35.67123,35.681874,35.675469]
sta_latitudes = [139.7662166,139.7632632,139.76602,139.761601,139.7596,139.7701,139.767044,139.765,139.773318,139.771758]
sta_ku = ["千代田区", "千代田区", "千代田区", "千代田区", "千代田区", "中央区", "中央区", "中央区", "中央区", "中央区"]
station_dic = pd.DataFrame({
    "駅名": sta_name,
    "経度": sta_longitudes,
    "緯度": sta_latitudes,
    "区": sta_ku
})

st.title("治安ナビ")
st.write("<h3 style='text-align: center;'>治安評価マップ</h3>", unsafe_allow_html=True)

select_station = st.sidebar.selectbox(
    "あなたの住みたいエリア（駅名）を選択してください。",
    sta_name
)

#------------------------------------------
# 選択肢のリストを作成
age_options = ["10代", "20代", "30代", "40代", "50代以上"]
gender_options = ["男性", "女性", "その他"]

# サイドバーに年代を表示
selected_age = st.sidebar.selectbox(
    "年代を選択してください",
    age_options
)

# サイドバーに性別を表示
selected_gender = st.sidebar.selectbox(
    "性別を選択してください",
    gender_options
)
#------------------------------------------



# 検索した駅の座標を設定
select_longitudes = station_dic[station_dic["駅名"] == select_station]["経度"]
select_latitudes = station_dic[station_dic["駅名"] == select_station]["緯度"]

# 地図の中心座標を設定
center = (select_longitudes, select_latitudes)

# Foliumマップオブジェクトを作成
m = folium.Map(location=center, zoom_start=15)

# GeoDataFrameをGeoJSON形式に変換
gdf_tokyo_station_json = gdf_tokyo_station.to_crs('EPSG:4326').to_json()

# GeoJSONデータをFoliumに追加
folium.GeoJson(gdf_tokyo_station_json, style_function=lambda x: {
    'fillColor': 'red',
    'fillOpacity': x['properties']['normalized_score'] if x['properties']['normalized_score'] is not None and x['properties']['normalized_score'] > 0 else 0,
    'color': 'grey',
    "weight" : 2,
    "fill_opacity": 0.7}).add_to(m)

# 選択した駅をピン表示する+円を描く
folium.Marker(location=[select_longitudes, select_latitudes], popup=select_station).add_to(m)
folium.Circle(location=[select_longitudes,select_latitudes],radius=500,color='#0000FF', fill_color='#0000FF').add_to(m)

df = pd.read_csv("output_tokyo.csv")

# 選択した駅名に対応するデータを抽出
select_station_data = df[df["station_name"].str.contains(select_station)]

# Markerメソッドでマーカーをプロット
for i, r in select_station_data.iterrows():
    folium.Marker(location = [r["緯度"], r["経度"]], popup = r["title"]).add_to(m)


# 地図を表示
st_data2 = st_folium(m, width=800, height=600)

# 選択した駅の区を設定
select_ku = station_dic.loc[station_dic["駅名"] == select_station,["区"]].to_string(index=False, header=False)

# 口コミデータを読み込む
value = pd.read_csv("kuchikomi.csv")

# 選択された区に対応するデータを抽出
selected_data = value[value["区"] == select_ku]

#------------------------------------------

# レーダーチャートを作成
fig = go.Figure()

# カテゴリ（評価項目）のリスト
categories = selected_data.columns

# 各カテゴリのスコアを取得
scores = selected_data.iloc[0].tolist()

# レーダーチャートのトレースを作成
fig.add_trace(go.Scatterpolar(
    r=scores,
    theta=categories,
    fill="toself",  # 領域を塗りつぶす
))

# レーダーチャートのレイアウト調整
fig.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, 5]  # スコアの範囲に合わせて調整
        )
    )
)

# Streamlitアプリを構築
st.write("<h3 style='text-align: center;'>住環境評価チャート</h3>", unsafe_allow_html=True)
st.plotly_chart(fig)

#------------------------------------------

#sogo = value.loc[value["区"] == select_ku, ["総合"]].to_string(index=False, header=False)
#kaimono = value.loc[value["区"] == select_ku, ["買い物"]].to_string(index=False, header=False)
#gurume = value.loc[value["区"] == select_ku, ["グルメ"]].to_string(index=False, header=False)
#sizen = value.loc[value["区"] == select_ku, ["自然"]].to_string(index=False, header=False)
#kosodate = value.loc[value["区"] == select_ku, ["子育て・教育"]].to_string(index=False, header=False)
#denbus = value.loc[value["区"] == select_ku, ["電車・バスの便利さ"]].to_string(index=False, header=False)
#kuruma = value.loc[value["区"] == select_ku, ["車の便利さ"]].to_string(index=False, header=False)

#st.write("総合：" + sogo)
#st.write("買い物：" + kaimono)
#st.write("グルメ：" + gurume)
#st.write("自然：" + sizen)
#st.write("子育て・教育：" + kosodate)
#st.write("電車・バスの便利さ：" + denbus)
#st.write("車の便利さ：" + kuruma)


st.write("<h3 style='text-align: center;'>新着・街レビュー</h3>", unsafe_allow_html=True)
# 選択した区の口コミレビューのデータを読み込む
review_file = "kuchikomi_comment_" +select_ku +".csv"
review = pd.read_csv(review_file)

#------------------------------------------

# 選択された年代と性別に合致するデータを抽出
selected_reviews = review[review["年代"].str.contains(selected_age) & review["年代"].str.contains(selected_gender)]

#------------------------------------------


#st.dataframe(selected_reviews)

# 抽出したデータを表示
for i in range(min(3, selected_reviews.shape[0])):
    review_people = selected_reviews["年代"].iloc[i]
    st.write(review_people)
    review_year = selected_reviews["住んでいた時期"].iloc[i]
    st.write("住んでいた時期：" + review_year)
    review_point = str(selected_reviews["評価点"].iloc[i])
    st.write("評価点：" + review_point)
    review_good = selected_reviews["満足"].iloc[i]
    st.write("満足ポイント：" + review_good)
    review_bad = selected_reviews["不満"].iloc[i]
    st.write("不満ポイント：" + review_bad)

    st.write("  ")
    st.write("  ")

