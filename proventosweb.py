import pandas as pd
import datetime as dt
import json
import requests
from bs4 import BeautifulSoup
import numpy as np
import re
import time

def percent_str_to_float(percent_str):
    decimal_str = percent_str.replace(',', '.')
    number_str = decimal_str.strip('%')
    number = float(number_str) / 100.0
    return number

def tratamento(prov, dob, boni, sub):
    dfp = None
    dfb = None
    dfbo = None
    dfs = None
    if prov is not None and not prov.empty:
        prov['Executado'] = prov['Pagamento']
        dfp = prov.loc[:, ['Tipo', 'Data COM', 'Executado', 'Valor', 'Valor Original']]
    if dob is not None and not dob.empty:
        dob['Executado'] = dob['Data COM']
        dob['Quantia From'] = dob['Quantia From'].astype(float)
        dob['Quantia To'] = dob['Quantia To'].astype(float)
        dob['Valor'] = dob.apply(lambda row: row['Quantia From'] if row['Quantia To'] == 1 else row['Quantia To'],
                                 axis=1)
        dfb = dob.loc[:, ['Tipo', 'Data COM', 'Executado', 'Valor']]

    if boni is not None and not boni.empty:
        boni['Executado'] = boni['Data de incorporação']
        boni['Valor'] = boni['Valor base']
        dfbo = boni.loc[:, ['Data COM', 'Executado', 'Valor']]
        dfbo['Tipo'] = 'Bonificação'

    if sub is not None and not sub.empty:
        sub['Quantia'] = sub['Valor Base']
        sub['Quantia'] = sub['Quantia'].str.replace('R$ ', '', regex=False).str.replace(',', '.', regex=False).astype(
            float)
        sub['Valor'] = sub['Percentual']
        sub['Valor'] = sub['Valor'].apply(percent_str_to_float)
        sub['Executado'] = ''
        for i in range(len(sub)):
            try:
                if sub.loc[i, 'Negociação'].str.split(' a ').str[1] != '31/12/9999':
                    sub.loc[i, 'Executado'] = sub.loc[i, 'Negociação'].str.split(' a ').str[1]
                elif sub.loc[i, 'Negociação'].str.split(' a ').str[0] != '31/12/9999':
                    sub.loc[i, 'Executado'] = sub.loc[i, 'Negociação'].str.split(' a ').str[0]
                else:
                    sub.loc[i, 'Executado'] = sub.loc[i, 'Data COM']
            except:
                sub.loc[i, 'Executado'] = None
        dfs = sub.loc[:, ['Data COM', 'Executado', 'Valor', 'Quantia']]
        dfs['Tipo'] = 'Subscrição'
    dfcons = pd.DataFrame(columns=['Tipo', 'Data COM', 'Executado', 'Valor', 'Valor Original', 'Quantia'])
    if dfp is None and dfb is None and dfbo is None and dfs is None:
        dfcons = None
    else:
        dfcons = pd.concat([dfp, dfb, dfbo, dfs], ignore_index=True)
        dfcons['Data COM'] = pd.to_datetime(dfcons['Data COM'], dayfirst=True).dt.date
        dfcons['Executado'] = dfcons['Executado'].replace('-', None)
        dfcons['Executado'] = pd.to_datetime(dfcons['Executado'], dayfirst=True).dt.date
        if sub is not None and not sub.empty:
            dfcons['Quantia'] = dfcons['Quantia'].replace({np.nan: None})
        if prov is not None and not prov.empty:
            dfcons['Valor Original'] = dfcons['Valor Original'].replace({pd.NA: None})
        dfcons.sort_values(by=['Tipo', 'Data COM'])
    return dfcons


def eventos(acao):
    acao = acao.upper()
    tipos = ['acoes', 'bdrs', 'fundos-imobiliarios', 'fiinfras', 'fiagros', 'etfs']
    t = 0
    dfin = None
    for tipo in tipos:
        url = 'https://statusinvest.com.br/' + tipo + '/' + acao
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        resposta = requests.get(url, headers=headers)
        amostra = resposta.text
        soup1 = BeautifulSoup(amostra, 'html.parser')
        if soup1.find('title').text != 'OPS. . .Não encontramos o que você está procurando | Status Invest':
            soup = soup1
            t = 1
            tipo2 = tipo

    if t == 1 and tipo2 != 'etfs':
        # Proventos
        value = soup.find('input', {'id': 'results'}).get('value')
        if value == '[]':
            print(acao + ' sem dividendos')
            df = None
        else:
            data = json.loads(value)
            try:
                df = pd.DataFrame(data)
                data = json.loads(value)
                df = df.loc[:, ['et', 'ed', 'pd', 'ov', 'v']]
                df = df.rename(
                    columns={'et': 'Tipo', 'ed': 'Data COM', 'pd': 'Pagamento', 'v': 'Valor', 'ov': 'Valor Original'})
            except:
                print(f"Erro desconhecido na ação {acao}")

        # Desdobramento ou Grupamento
        a = soup.find('div', class_='white')
        b = a.find('div', class_='pt-5')
        if b != None:
            c = b.find('div', class_='card-body')
            texto = c.text.strip()
            if texto != 'NÃO HÁ DESDOBRAMENTO OU GRUPAMENTO':
                dobs = dobramento(texto)
            else:
                dobs = None
        else:
            dobs = None
        # Bonificação
        b1 = a.find('div', class_='card p-2 p-xs-3')
        if b1 != None:
            c1 = b1.find('div', class_='card-body')
            texto1 = c1.text.strip()
            if texto1 != "NÃO HÁ BONIFICAÇÃO":
                bons = bonificacao(texto1)
                if bons['Ativo emitido'].unique() != acao:
                    print('Ativo diferente emitido')
            else:
                bons = None
        else:
            bons = None
        # Subscrição
        a2 = soup.find_all('div', class_='pt-5')[2]
        b2 = a2.find_all('strong')
        if len(b2) > 0:
            subs = subscricao(b2)
        else:
            subs = None
        dfin = tratamento(df, dobs, bons, subs)
        if dfin is not None:
            dfin['Ativo'] = acao
    return dfin


def dobramento(strings):
    pattern = r'(Grupamento|Desdobramento)[\s\S]*?Data do anúncio\n([\d/]+)[\s\S]*?Data COM\n([\d/]+)[\s\S]*?Fator\n([\d,]+) para ([\d,]+)'
    tipos = []
    datas_announced = []
    datas_com = []
    quantias_from = []
    quantias_to = []
    for s in [strings]:
        matches = re.findall(pattern, s)
        for match in matches:
            tipos.append(match[0])
            datas_announced.append(match[1])
            datas_com.append(match[2])
            quantias_from.append(match[4].replace(',', '.'))
            quantias_to.append(match[3].replace(',', '.'))
    df = pd.DataFrame({
        'Tipo': tipos,
        'Data Anuncio': datas_announced,
        'Data COM': datas_com,
        'Quantia From': quantias_from,
        'Quantia To': quantias_to
    })
    return df


def bonificacao(texto):
    records = re.split(r'\n{2,}Data do anúncio', texto)
    if records and not records[0].strip():
        records.pop(0)
    data = []
    for record in records:
        record = re.sub(r'\n{2,}', '\n', record)
        record = 'Data do anúncio' + record
        date_anuncio = re.search(r'Data do anúncio\n([\d/]+)', record)
        date_com = re.search(r'Data com\n([\d/]+)', record)
        date_ex = re.search(r'Data ex\n([\d/]+)', record)
        date_incorporacao = re.search(r'Data de incorporação\n([\d/]+)', record)
        ativo = re.search(r'Ativo emitido\n([\w]+)', record)
        valor_base = re.search(r'Valor base\nR\$ ([\d,]+)', record)
        proporcao = re.search(r'Proporção\n([\d,]+)%', record)
        row = {
            'Data do anúncio': date_anuncio.group(1) if date_anuncio else None,
            'Data COM': date_com.group(1) if date_com else None,
            'Data EX': date_ex.group(1) if date_ex else None,
            'Data de incorporação': date_incorporacao.group(1) if date_incorporacao else None,
            'Ativo emitido': ativo.group(1) if ativo else None,
            'Valor base': valor_base.group(1) if valor_base else None,
            'Proporção': proporcao.group(1) if proporcao else None,
        }
        data.append(row)
    df = pd.DataFrame(data)
    df = df[
        ['Data do anúncio', 'Data COM', 'Data EX', 'Data de incorporação', 'Ativo emitido', 'Valor base', 'Proporção']]
    return df


def subscricao(b):
    anuncio = []
    fimd = []
    datacom = []
    incop = []
    negoc = []
    valb = []
    perc = []
    atv = []
    for j in range(int(len(b) / 8)):
        i = j * 8
        anuncio.append(b[i].text.strip())
        fimd.append(b[i + 3].text.strip())
        datacom.append(b[i + 1].text.strip())
        incop.append(b[i + 4].text.strip())
        negoc.append(b[i + 2].text.strip())
        valb.append(b[i + 5].text.strip())
        perc.append(b[i + 6].text.strip())
        atv.append(b[i + 7].text.strip())
    df = pd.DataFrame({
        'Data Anuncio': anuncio,
        'Data COM': datacom,
        'Fim Subscrição': fimd,
        'Incorporação': incop,
        'Ativo': atv,
        'Negociação': negoc,
        'Valor Base': valb,
        'Percentual': perc
    })
    return df

def provlista(acoeslista, testtime=0):
    if testtime ==1:
        import time
        dfprov = pd.DataFrame(columns=['Ativo', 'Tipo', 'Data COM', 'Executado', 'Valor', 'Valor Original', 'Quantia'])
        acoes = acoeslista.unique().tolist()
        cortes =[0.25,0.5,0.75,1]
        print('Buscando proventos de '+str(len(acoes))+' ações!')
        start_time = time.time()
        longest_atv = None
        longest_time = 0
        j = 0
        for i, atv in enumerate(acoes):
            if i/len(acoes)>cortes[j]:
                print('Já foi '+str(cortes[j]*100)+"% das ações!")
                j = j+1
            print(f'Processing {atv} ({i+1}/{len(acoes)})...')
            atv_start_time = time.time()
            dfnovo = eventos(atv)
            atv_time = time.time() - atv_start_time
            if atv_time > longest_time:
                longest_atv = atv
                longest_time = atv_time
            if dfnovo is not None:
                dfprov = pd.concat([dfprov,dfnovo])
        print('Acabou!')
        total_time = time.time() - start_time
        print(f'Tempo total: {total_time:.2f} segundos')
        print(f'Média por ativo: {(total_time/len(acoes)):.2f} segundos')
        print(f'Tempo máximo: {longest_atv} ({longest_time:.2f} segundos)')
    else:
        dfprov = pd.DataFrame(columns=['Ativo', 'Tipo', 'Data COM', 'Executado', 'Valor', 'Valor Original', 'Quantia'])
        acoes = acoeslista.unique().tolist()
        cortes =[0.25,0.5,0.75]
        print('Buscando proventos de '+str(len(acoes))+' ações!')
        j = 0
        for i in range(len(acoes)):
            if i/len(acoes)>cortes[j]:
                print('Já foi '+str(cortes[j]*100)+"% das ações!")
            atv = acoes[i]
            dfnovo = eventos(atv)
            if dfnovo is not None:
                dfprov = pd.concat([dfprov,dfnovo])
        print('Acabou!')
    return dfprov
