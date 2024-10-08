import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re


# Configuring authentication with Google Sheets
def authenticate_with_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # reading secrets.toml
    try:
        service_account_info = st.secrets["google_credentials"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Erro na autenticação: {e}")
        raise

# Function to load data from a specific worksheet
def load_sheet_data(sheet_url, sheet_name):
    gc = authenticate_with_google_sheets()
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.worksheet(sheet_name)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty:
        st.error("Erro: A planilha está vazia ou os dados não foram carregados corretamente.")
        return None
    return df
    
def main():
    if "sheets" in st.secrets:
        NAME = st.secrets["sheets"]["name"]
        URL = st.secrets["sheets"]["url"]

        df = load_sheet_data(URL, NAME)
        return df
        
def transform_dataframe(df : pd.DataFrame):
    # function to transform the dataframe
    df = df.rename(columns={
        'Timestamp': 'Data/Hora',
        'Nome e sobrenome': 'Nome_Completo',
        'Email': 'Email',
        'Telefone (com DDD)': 'Telefone',
        'Link do linkedin': 'LinkedIn',
        'Qual país e cidade você mora? Coloque exatamente no formato abaixo, com País - Cidade (Estado) e o estado entre parêntesis.\nEx: Brasil - Piracicaba (SP)':'Localização',
        'Tem disponibilidade de mudança?': 'Disponibilidade de Mudança',
        'Existe alguma restrição quanto ao regime de trabalho?': 'Regime de Trabalho',
        'Formação acadêmica. Coloque o curso que fez + faculdade + ano de conclusão (ou previsão de conclusão). Se tiver pós-graduação ou mestrado, coloque também! Separe-os com ponto e vírgula.\nSe nunca fez algum tipo de graduação e nem está fazendo, coloque NA.\n \nUse o modelo abaixo:\nBacharelado engenharia química - Unicamp - conclusão 2019;\nPós-graduação data science - Unicamp - conclusão 2020; \nMestrado em data sciece para marketing - Unicamp - conclusão 2025': 'Formação Acadêmica',
        'Você já tem experiência na área de dados? Não precisa ser com o cargo oficial de analista ou cientista, mas algo que possa comprovar que você já teve experiências com dados': 'Experiência em Dados',
        'Se marcou sim acima, descreva brevemente qual sua experiência. \nEx: Sou cientista de dados tech lead. Atuei como cientista de dados em diversas empresas no Brasil, desenvolvendo modelos de machine learning e análises estatísticas. Atualmente atuo e moro em Portugal.': 'Descrição da Experiência',
        'Qual seu cargo pretentido para agora? \nTenha em vista seu cargo atual. Se você é junior, você pode procurar de junior ou pleno. Se nunca teve experiência, pode procurar por junior ou, se também estiver na faculdade, por estágios.\nNão marque todas as opções de senioridade! Veja a que faz realmente sentido para agora': 'Cargo Pretendido',
        'Qual seu cargo atual? \nSe está desempregado, escreva sua experiência anterior caso seja relavante para o mundo de dados ou "Desempregado - estudando para entrar na área de dados por cursos livres". \nSe estiver desempregado, não tiver tido experiência relavante para dados mas é apto a aplicar para estágios (cursando bacharelado ou tecnólogo) escreva "Estudante".': 'Cargo Atual',
        'Se você está estudando, qual é o regime?': 'Regime de Estudo',
        'Quais skills você já estudou/domina?': 'Skills Dominadas',
        'Qual dos meus cursos você cursa/cursou? Se for aluno de ambos, marque ambos': 'Cursos Cursados',
        'Qual seu nível de inglês?': 'Nível de Inglês',
        'Você permite que seus dados pessoais sejam compartilhados, para fins de recrutamento?':'Divulgação'
    })
    
    # transform Data/Hora type to datetime
    if 'Data/Hora' in df.columns:
        df['Data/Hora'] = pd.to_datetime(df['Data/Hora'], errors='coerce')
    
    # drop the duplicated rows keeping currently data
    if 'Data/Hora' in df.columns:
        df = df.sort_values('Data/Hora', ascending=False).drop_duplicates('Email')
                
    # slip desired position by ,
    df['Cargo Pretendido'] = df['Cargo Pretendido'].str.split(',').apply(lambda x: [i.strip() for i in x] if isinstance(x, list) else x)
    df = df.explode('Cargo Pretendido').reset_index(drop=True)

    # creating a new column with Senioridade
    df[['Cargo Pretendido', 'Senioridade']] = df['Cargo Pretendido'].str.split('-', expand=True)
    df['Senioridade'] = df['Senioridade'].str.lower()
    
    # separe localização column into Country, City and state
    # Regex pattern to match the location format
    pattern = re.compile(r'^\s*(?:(?P<País>[A-Za-zÀ-ÖØ-öø-ÿ]+(?:\s*[A-Za-zÀ-ÖØ-öø-ÿ]+)*)\s*-\s*)?(?P<Cidade>[A-Za-zÀ-ÖØ-öø-ÿ]+(?:\s*[A-Za-zÀ-ÖØ-öø-ÿ]+)*)(?:\s*\(\s*(?P<Estado>[A-Za-zÀ-ÖØ-öø-ÿ]{2,})\s*\))?\s*$', re.IGNORECASE)

    # Applying the regex to the 'Localização' column
    df[['País', 'Cidade', 'Estado']] = df['Localização'].str.extract(pattern)

    # heandeling with null values in Country Column
    siglas = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']

    df.loc[df['Estado'].isin(siglas), 'País'] = 'Brasil'

    for index, row in df.iterrows():
      # Get the non-null value in the row for País, Cidade, or Estado
      non_null_value = row[['País', 'Cidade', 'Estado']].dropna().values
      if len(non_null_value) > 0:
          fill_value = non_null_value[0]
          # Fill NaN values in the row with the found non-null value
          df.at[index, 'País'] = fill_value if pd.isna(row['País']) else row['País']
          df.at[index, 'Cidade'] = fill_value if pd.isna(row['Cidade']) else row['Cidade']
          df.at[index, 'Estado'] = fill_value if pd.isna(row['Estado']) else row['Estado']
          
    # ensure that the column will be string and removing "+" character
    df['Telefone'] = df['Telefone'].astype(str).str.replace('+', '', regex=False)
    
    #ensure some columns as string values
    string_columns = [
        'Divulgação',
        'Nível de Inglês',
        'Descrição da Experiência',
        'Regime de Estudo',
        'Formação Acadêmica'
    ]
    for column in string_columns:
        if column in df.columns:
            df[column] = df[column].astype(str)

    #fill null values
    df['Divulgação'] = df['Divulgação'].replace('None', 'Sim')
    df['Nível de Inglês'] = df['Nível de Inglês'].replace('None', 'Não respondido')
    df['Descrição da Experiência'] = df['Descrição da Experiência'].replace('None', 'Sem experiência')
    df['Regime de Estudo'] = df['Regime de Estudo'].replace('None', 'Não respondido')
    df['Formação Acadêmica'] = df['Formação Acadêmica'].replace('None', 'Não respondido')
    
        
    return df

if __name__ == "__main__":
    main()