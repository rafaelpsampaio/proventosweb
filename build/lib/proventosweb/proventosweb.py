import pandas as pd
import json
import requests
from bs4 import BeautifulSoup
import numpy as np
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
        boni['Valor'] = boni['Valor Base']
        dfbo = boni.loc[:, ['Data COM', 'Executado', 'Valor', 'Proporção']]
        dfbo['Tipo'] = 'Bonificação'

    if sub is not None and not sub.empty:
        sub['Quantia'] = sub['Valor Base']
        sub['Valor'] = sub['Percentual']
        sub['Executado'] = sub['Negociação']
        dfs = sub.loc[:, ['Data COM', 'Executado', 'Valor', 'Quantia']]
        dfs['Tipo'] = 'Subscrição'
    dfcons = pd.DataFrame(columns=['Tipo', 'Data COM', 'Executado', 'Valor', 'Valor Original', 'Quantia', 'Proporção'])
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
        if boni is not None and not prov.empty:
            dfcons['Proporção'] = dfcons['Proporção'].replace({pd.NA: None})
        dfcons.sort_values(by=['Tipo', 'Data COM'])
    return dfcons


def dobramento(strings):
    data = []
    for string in strings:
        txt = string.text
        lines = txt.split('\n')
        tipo = lines[3].strip()
        data_anuncio = lines[8].strip()
        data_com = lines[12].strip()
        fator_line = lines[16].strip()
        quantia_values = fator_line.split(' ')
        quantia_from = float(quantia_values[0].replace(',', '.'))
        quantia_to = float(quantia_values[2].replace(',', '.'))
        data.append([tipo, data_anuncio, data_com, quantia_from, quantia_to])
    df = pd.DataFrame(data, columns=['Tipo', 'Data Anuncio', 'Data COM', 'Quantia From', 'Quantia To'])
    return df


def bonificacao(texto):
    dfs = []  # List to store individual DataFrames

    for string in texto:
        txt = string.text
        lines = txt.split('\n')

        tipo = "Bonificação"  # Fixed value
        data_anuncio = lines[lines.index('Data do anúncio') + 1].strip()
        data_com = lines[lines.index('Data com') + 1].strip()
        data_ex = lines[lines.index('Data ex') + 1].strip()
        data_incorporacao = lines[lines.index('Data de incorporação') + 1].strip()
        ativo_emitido = lines[lines.index('Ativo emitido') + 1].strip()

        valor_base = float(lines[lines.index('Valor base') + 1].replace('R$', '').strip().replace(',', '.'))
        proporcao = float(lines[lines.index('Proporção') + 1].replace('%', '').strip().replace(',', '.')) / 100

        data = {
            'Tipo': [tipo],
            'Data do anúncio': [data_anuncio],
            'Data COM': [data_com],
            'Data EX': [data_ex],
            'Data de incorporação': [data_incorporacao],
            'Ativo Emitido': [ativo_emitido],
            'Valor Base': [valor_base],
            'Proporção': [proporcao]
        }

        df = pd.DataFrame(data)
        dfs.append(df)

    df_concat = pd.concat(dfs, ignore_index=True)
    df_concat = df_concat[
        ['Data do anúncio', 'Data COM', 'Data EX', 'Data de incorporação', 'Ativo Emitido', 'Valor Base', 'Proporção']]
    return df_concat


def subscricao(texto):
    dfs = []  # List to store individual DataFrames

    for string in texto:
        txt = string.text
        lines = txt.split('\n')

        data_anuncio = lines[lines.index('Anúncio') + 1].strip()
        data_com = lines[lines.index('DATA COM') + 1].strip()
        fim_subscricao = lines[lines.index('Fim de subscrição') + 1].strip()
        incorporacao = lines[lines.index('Incorporação') + 1].strip()
        negociacao = lines[lines.index('Negociação') + 1].strip().split(' a ')[1]
        valor_base_str = lines[lines.index('Valor base') + 1].replace('R$', '').strip().replace('.', '')
        valor_base = float(valor_base_str.replace(',', '.'))
        percentual = float(lines[lines.index('Percentual') + 1].replace('%', '').strip().replace(',', '.')) / 100
        ativo = lines[lines.index('Ativo emitido') + 1].strip()

        data = {
            'Data Anuncio': [data_anuncio],
            'Data COM': [data_com],
            'Fim Subscrição': [fim_subscricao],
            'Incorporação': [incorporacao],
            'Ativo': [ativo],
            'Negociação': [negociacao],
            'Valor Base': [valor_base],
            'Percentual': [percentual]
        }

        df = pd.DataFrame(data)
        dfs.append(df)

    df_concat = pd.concat(dfs, ignore_index=True)
    return df


def provlista(acoes, testtime=0):
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    dfprov = pd.DataFrame(columns=['Ativo', 'Tipo', 'Data COM', 'Executado', 'Valor', 'Valor Original', 'Quantia'])
    cortes = [0.25, 0.5, 0.75, 1]
    if testtime == 1:
        print('Buscando proventos de ' + str(len(acoes)) + ' ações!')
        start_time = time.time()
        longest_atv = None
        longest_time = 0
        j = 0
        for i, atv in enumerate(acoes):
            if i / len(acoes) >= cortes[j]:
                print('Já foi ' + str(cortes[j] * 100) + "% das ações!")
                j = j + 1
            print(f'Processando {atv} ({i + 1}/{len(acoes)})...')
            atv_start_time = time.time()
            dfnovo = eventos(atv, session, headers)
            atv_time = time.time() - atv_start_time
            if atv_time > longest_time:
                longest_atv = atv
                longest_time = atv_time
            if dfnovo is not None:
                dfprov = pd.concat([dfprov, dfnovo])
        if 'Valor Original' in dfprov.columns:
            dfprov['Valor Original'] = dfprov['Valor Original'].replace({pd.NA: None})
        if 'Quantia' in dfprov.columns:
            dfprov['Quantia'] = dfprov['Quantia'].replace({np.nan: None})
        if 'Proporção' in dfprov.columns:
            dfprov['Proporção'] = dfprov['Proporção'].replace({pd.NA: None})
        print('Acabou!')
        total_time = time.time() - start_time
        print(f'Tempo total: {total_time:.2f} segundos')
        print(f'Média por ativo: {(total_time / len(acoes)):.2f} segundos')
        print(f'Tempo máximo: {longest_atv} ({longest_time:.2f} segundos)')
    elif testtime == 2:
        for i in range(len(acoes)):
            atv = acoes[i]
            dfnovo = eventos(atv, session, headers)
            if dfnovo is not None:
                dfprov = pd.concat([dfprov, dfnovo])
        if 'Valor Original' in dfprov.columns:
            dfprov['Valor Original'] = dfprov['Valor Original'].replace({pd.NA: None})
        if 'Quantia' in dfprov.columns:
            dfprov['Quantia'] = dfprov['Quantia'].replace({np.nan: None})
        if 'Proporção' in dfprov.columns:
            dfprov['Proporção'] = dfprov['Proporção'].replace({pd.NA: None})
    else:
        print('Buscando proventos de ' + str(len(acoes)) + ' ações!')
        j = 0
        for i in range(len(acoes)):
            if i / len(acoes) >= cortes[j]:
                print('Já foi ' + str(cortes[j] * 100) + "% das ações!")
                j += 1
            atv = acoes[i]
            dfnovo = eventos(atv, session, headers)
            if dfnovo is not None:
                dfprov = pd.concat([dfprov, dfnovo])
        if 'Valor Original' in dfprov.columns:
            dfprov['Valor Original'] = dfprov['Valor Original'].replace({pd.NA: None})
        if 'Quantia' in dfprov.columns:
            dfprov['Quantia'] = dfprov['Quantia'].replace({np.nan: None})
        if 'Proporção' in dfprov.columns:
            dfprov['Proporção'] = dfprov['Proporção'].replace({pd.NA: None})
        print('Acabou!')
    return dfprov


def procurandotipo(acao, tempo, session, headers, tipos):
    tipo2 = None
    soup = None
    for tipo in tipos:
        try:
            url = 'https://statusinvest.com.br/' + tipo + '/' + acao
            resposta = session.get(url, headers=headers, timeout=tempo)
            if resposta.status_code == 200:
                amostra = resposta.text
                soup1 = BeautifulSoup(amostra, 'html.parser')
                if soup1.find('title').text != 'OPS. . .Não encontramos o que você está procurando | Status Invest':
                    soup = soup1
                    tipo2 = tipo
                    break
        except requests.exceptions.RequestException:
            continue
    return soup, tipo2


def eventos(acao, session=0, headers=0):
    acao = acao.upper()
    tempos = [x / 10 for x in range(3, 10)]
    if acao[-2:] == '34':
        tipos = ['bdrs', 'acoes', 'fundos-imobiliarios', 'fiinfras', 'fiagros', 'etfs']
    elif acao[-2:] == '11':
        tipos = ['fundos-imobiliarios', 'acoes', 'fiinfras', 'fiagros', 'etfs', 'bdrs']
    else:
        tipos = ['acoes', 'fundos-imobiliarios', 'fiinfras', 'fiagros', 'etfs', 'bdrs']
    if session == 0:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        session = requests.Session()
    for tempo in tempos:
        soup, tipo2 = procurandotipo(acao, tempo, session, headers, tipos)
        if soup is not None:
            break
    dfin = None
    if soup is None:
        print("Tipo não encontrado")
    else:
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
        caixas = soup.find_all('div', class_='card p-2 p-xs-3')
        dobs = None
        bons = None
        subs = None
        for i in range(len(caixas)):
            texto = caixas[i].find('h3').text
            insert = caixas[i].find_all('div',
                                        class_="d-flex justify-between align-items-center flex-wrap flex-md-nowrap")
            if texto == "DESDOBRAMENTO/GRUPAMENTO":
                if len(insert) > 0:
                    dobs = dobramento(insert)
            elif texto == "BONIFICAÇÃO":
                if len(insert) > 0:
                    bons = bonificacao(insert)
            elif texto == "SUBSCRIÇÃO":
                A = caixas[i].find_all('div',
                                       class_="d-flex justify-between align-items-center flex-wrap flex-lg-nowrap")
                if len(A) > 0:
                    subs = subscricao(A)
            else:
                print(texto)
        dfin = tratamento(df, dobs, bons, subs)
        if dfin is not None:
            dfin['Ativo'] = acao
    return dfin
