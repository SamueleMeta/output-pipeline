# Import libraries
import plotly.graph_objects as go
import plotly.express as px
from random import randint
import pandas as pd
import numpy as np
from math import *
import plotly
import json
import csv
import sys
import os
import io

def start_annotate_task__(result, task, task_run):
    print("\n\nStarting annotation task")
    df_run=pd.read_csv(task_run)
    df_output=pd.read_csv(result)
    df_task=pd.read_csv(task)
    # Clean the dataset
    df_run.reset_index(inplace=True)
    df_run.drop(df_run.columns.difference(
        ['task_id', 'info_0', 'info_1', 'info_2', 'info_3', 'info_4_0', 'info_4_1', 'info_4_2', 'info_4_3', 'info_5',
         'info_6', 'info_7', 'info_8', 'info_9', 'info_10', 'info_11', 'media_url']), axis=1, inplace=True)
    # Columns containing the answer to each question
    questions = ['info_0', 'info_1', 'info_2', 'info_3', 'info_4_0', 'info_4_1', 'info_4_2', 'info_4_3', 'info_5',
                 'info_6', 'info_7', 'info_8', 'info_9', 'info_10', 'info_11']
    id_column = 'task_id'
    df_run_grouped = pd.DataFrame(df_run[id_column].unique())
    df_run_grouped.columns = [id_column]
    # Majority vote for each id on each question
    for field in questions:
        df_field = df_run[df_run[field].isna() == False].groupby(id_column)[field].apply(
            lambda x: x.value_counts().index[0]).reset_index()
        df_run_grouped = df_run_grouped.join(df_field.set_index(id_column), on=id_column)
    df_image_url = df_task.drop(df_task.columns.difference(['id', 'info_image']), axis=1)
    df_run_grouped = pd.merge(df_image_url, df_run_grouped, left_on='id', right_on='task_id')
    df_image_url = df_output.drop(df_output.columns.difference(['id', 'task_id']), axis=1)
    df_run_grouped = pd.merge(df_image_url, df_run_grouped, left_on='task_id', right_on='task_id')
    # Merge with info of the tweet and clean final dataset
    df_result = pd.merge(df_run_grouped, df_task, left_on='task_id', right_on='id')
    df_result_geoloc_ok = df_result[df_result["info_11"] != "Surely not"]
    print("\nAnnotation task ended.")
    return df_result_geoloc_ok


def clean_str(my_list):
    new_list = []
    for i in list(my_list):
        i_stripped = (i.replace('"', "")).strip()
        new_list.append(i_stripped)
    return new_list


def preprocess_choices(answer, info_number):
    Noncleaned_choices = list(set(answer[info_number]))
    cleaned_choices = [x for x in Noncleaned_choices if (str(x) != 'nan')]
    return cleaned_choices


def total_ans(list_choice, data, threshold):
    t = 0
    index_list = []
    for i in list_choice:
        t = t + data[i]
    data['total_responses'] = t
    per = data['total_responses'].astype(int) / sum(data['total_responses'].astype(int)) * 100
    data['response %'] = round(per, 2)
    for idx, row in data.iterrows():
        if row['total_responses'] > int(threshold):
            for i in list_choice:
                if row[i] != 0:
                    data[i][idx] = round((row[i] / row['total_responses'] * 100), 2)
        else:
            index_list.append(idx)
    data = data.drop(data.index[index_list])
    return data


def grouping_answers(data, choice_list, result, info_num):
    # Ignore the warning
    pd.set_option('mode.chained_assignment', None)
    data = data.reset_index(level=0, drop=True)
    if 'Not answered' in choice_list:
        choice_list.remove('Not answered')
    if 'Cannot tell' in choice_list:
        choice_list.remove('Cannot tell')
    for choice in choice_list:
        data[choice] = 0.0
        for index, row in result.iterrows():
            if (row['info_country_code'] in list(data['Alpha3'])) & (row[info_num] == choice):
                j = list(data['Alpha3']).index(row['info_country_code'])
                data[choice][j] = data[choice][j] + 1
    return data


def start_map_creation__(annotate_result, map_infos, threshold, start_from_previous_task=False):
    # Import from https://geojson-maps.ash.ms/
    from urllib.request import urlopen
    with urlopen('https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json') as response:
      map_data = json.load(response)

    map_data2 = map_data
    # mapbox token
    mapbox_accesstoken = "pk.eyJ1IjoiYW5kcmVhbWFyaW5vMTQ1IiwiYSI6ImNrZjQ0dm9rajA5a3YydW80NXYzdzUwcHcifQ.ywC9wsjnsZS2uP3m403YJw"
    iso_code = pd.read_csv('iso.csv')
    iso_list = iso_code.loc[:, ['Country', 'Alpha2', 'Alpha3']]
    df4 = iso_list
    a2 = list(iso_list['Alpha2'])
    a2 = clean_str(a2)
    iso_list['Alpha2'] = a2
    a3 = list(iso_list['Alpha3'])
    a3 = clean_str(a3)
    iso_list['Alpha3'] = a3

    map_number = len(map_infos)

    trace1 = []

    for i in range(map_number):
      clean_result = annotate_result
      cleanedList_choices = preprocess_choices(clean_result, map_infos[i][0])
      data = grouping_answers(df4, cleanedList_choices, clean_result, map_infos[i][0])
      data = total_ans(cleanedList_choices, data, threshold)
      for col in data.columns:
        data[col] = data[col].astype(str)
      data['text'] = data['Country'] + '<br>'
      for t in cleanedList_choices:
        data['text'] += ' ' + t + ' : ' + data[t] + '%' + '<br>'
      data['text'] += 'Total responses : ' + data['total_responses'] + '<extra>' + data['Alpha3'] + '</extra>'
      suburbs = data['text'].str.title().tolist()
      trace1.append(go.Choroplethmapbox(
          geojson=map_data2,
          locations=data.Alpha3.tolist(),
          z=data[map_infos[i][2]],
          zmin=0,
          zmax=100,
          colorscale='RdYlGn',
          text=suburbs,
          colorbar=dict(thickness=10, ticklen=2),
          marker_line_width=0,
          marker_opacity=0.7,
          marker_line_color='white',
          visible=False,
          subplot='mapbox1',
          colorbar_tickprefix='%',
          colorbar_title=map_infos[i][1],
          hovertemplate=data['text']))
      data.to_csv(f'{map_infos[i][1].lower()}_{map_infos[i][2].lower()}_map.csv')

    trace1[0]['visible'] = True
    # from django.conf import setting
    # start latitude and longitude values
    latitude = 50
    longitude = 10
    layout = go.Layout(
        title={'text': 'CrowdVsCovid',
               'font': {'size': 24,
                        'family': 'Arial'}},
        autosize=True,
        mapbox1=dict(
            domain={'x': [0, 0.97], 'y': [0, 0.98]},
            center=dict(lat=latitude, lon=longitude),
            accesstoken=mapbox_accesstoken,
            zoom=0.8),
        margin=dict(l=20, r=20, t=70, b=20),
        width=980, height=900,
        paper_bgcolor='rgb(204, 204, 204)',
        plot_bgcolor='rgb(204, 204, 204)',

    );

    buttons_ = []
    for i in range(map_number):
      visibility = [False for _ in range(map_number)]
      visibility[i] = True
      buttons_.append(dict(args=['visible', visibility], label=f'{map_infos[i][1]} : {map_infos[i][2]}', method='restyle')) 

    layout.update(updatemenus=list([
        dict(x=0,
             y=1,
             xanchor='left',
             yanchor='bottom',
             buttons=buttons_,
             )]));

    layout.update(annotations=[go.layout.Annotation(showarrow=False,xanchor='left',x=1,xshift=-800,yanchor='top',y=0.05,
                                                    yshift=-40, font=dict(family='Arial',size=12),
                                                    text=f'Ref.{map_infos[i][1].lower()}_{map_infos[i][2].lower()}')])
    fig = go.Figure(data=trace1, layout=layout)
    fig.write_html(f'{map_infos[i][1].lower()}_{map_infos[i][2].lower()}_map.html')
    print("\nMap creation task ended")


with open('106_social_distancing_and_masks_result.csv', encoding="utf8") as f:
  result_data = f.read()
  result = io.StringIO(result_data)

with open('106_social_distancing_and_masks_task.csv', encoding="utf8") as f:
  task_data = f.read()
  task = io.StringIO(task_data)

with open('106_social_distancing_and_masks_task_run.csv', encoding="utf8") as f:
  task_run_data = f.read()
  task_run = io.StringIO(task_run_data)

map_infos = [('info_3', 'wearing_masks', 'Yes')]
threshold = input("How many responses have to be considered significant?")
annotated = start_annotate_task__(result, task, task_run)
start_map_creation__(annotated, map_infos, threshold)