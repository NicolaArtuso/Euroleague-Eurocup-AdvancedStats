import pandas as pd
import requests
import json
import time
from Team import TeamStat
from Player import PlayerStat

#Funzione per trovare il codice squadra del team di casa
def find_home(df): 
    row = df[df['POINTS_A'] != 0.0].iloc[0]
    return row['CODETEAM']
    
#Funzione per trovare il codice squadra del team ospite
def find_guest(df):
    row = df.loc[df['POINTS_B'] != 0.0].iloc[0]
    return row['CODETEAM']   

#Funzione per convertire i dati dalla forma minuti:secondi al conteggio dei soli secondi 
def convert_to_seconds(time_str):
    minutes, seconds = time_str.split(':')
    return int(minutes) * 60 + int(seconds)

#Funzione per richiedere all'utente di quale partita intende visualizzare le statistiche
def create_url():
    # richiede all'utente di inserire il game code e il season code
    season_code = input("Inserisci il season code: ")
    game_code = input("Inserisci il game code: ")

    # costruisce l'URL utilizzando i valori inseriti dall'utente
    link = f"https://live.euroleague.net/api/PlaybyPlay?gamecode={game_code}&seasoncode=E{season_code}"
    
    #Fa una richiesta GET all'URL e restituisce la risposta
    response = requests.get(url=link).json()
    return response

def main():
    r = create_url()
    
    #Trovo il nome di ciascuna colonna del dataset attraverso le chiavi
    table_headers = list(r['FirstQuarter'][0].keys())
    #Aggiungo la colonna quarter per inserire l'informazione riguardo al quarto in cui si sta svolgendo l'azione
    df_cols = ['QUARTER']+table_headers
    #Creo il dataframe a partire dal nome delle colonne
    df = pd.DataFrame(columns=df_cols)
    quarters = ['FirstQuarter','SecondQuarter','ThirdQuarter','ForthQuarter','ExtraTime']
    
    #Riempio il dataframe
    for q in quarters:
        action = [None]*len(r[q])
        for i in range(len(r[q])): 
            action[i] = list(r[q][i].values()) 
        temp_df1 = pd.DataFrame(action,columns=table_headers) 
        temp_df2 = pd.DataFrame({'QUARTER':[q for i in range(len(r[q]))]})
        temp_df3 = pd.concat([temp_df2,temp_df1],axis=1) 
        df = pd.concat([df,temp_df3],axis=0)
    df = df.drop_duplicates().reset_index(drop=True)
    del (temp_df1,temp_df2,temp_df3)
    
    #Elimino le colonne che non mi servono (sono dati ridondanti o inutili ai fini dell'analisi)
    df = df.drop(['TYPE','NUMBEROFPLAY','COMMENT','MINUTE','DORSAL'],axis=1)
    
    #Sostituisco i vari NA nella colonna dei punti con il valore 0
    df['POINTS_A'] = df['POINTS_A'].fillna(0.0)
    df['POINTS_B'] = df['POINTS_B'].fillna(0.0)
    
    #Trasformo le variabili dei punti in interi
    df['POINTS_A'] = df['POINTS_A'].astype(int)
    df['POINTS_B'] = df['POINTS_B'].astype(int)
    
    #Correggo il markertime per inizio e fine quarto
    df.loc[df['PLAYTYPE']=='BP', 'MARKERTIME'] = '10:00'
    df.loc[df['PLAYTYPE']=='EP', 'MARKERTIME'] = '00:00'
    df.loc[df['PLAYTYPE']=='EG', 'MARKERTIME'] = '00:00'
    
    
    #Converto il markertime in secondi 
    df['MARKERTIME'] = df['MARKERTIME'].apply(convert_to_seconds)
    
    #Modifico i vari codici presenti per evitare spazi vuoti inutili
    df['CODETEAM'] = df['CODETEAM'].str.strip()
    df['PLAYER_ID'] = df['PLAYER_ID'].str.strip()
    df['PLAYER'] = df['PLAYER'].str.strip()
    
    #Seleziono i "tiri liberi finali" ovvero i tiri liberi che segnalano un cambio di possesso
    dfFT = pd.DataFrame(df.loc[df['PLAYTYPE'].isin(['FTM','FTA'])]) 
    condizione = (dfFT['PLAYTYPE'] == 'FTM') & (dfFT['MARKERTIME'].shift(-1) != dfFT['MARKERTIME'] )
    dfFT.loc[condizione, 'PLAYTYPE'] = 'FTMF'
    df.update(dfFT[dfFT['PLAYTYPE'] == 'FTMF'])
    del dfFT
    
    #Seleziono i "field goal foul" ovvero i tiri segnati subendo fallo, che dunque non segnalano un cambio di possesso
    dfFG = pd.DataFrame(df.loc[df['PLAYTYPE'].isin(['FTM','FTA','3FGM','2FGM','FTMF'])]) 
    condizione1 = (dfFG['PLAYTYPE'] == '2FGM') & (dfFG['PLAYTYPE'].shift(-1).isin(['FTM','FTMF','FTA']))
    condizione2 = (dfFG['PLAYTYPE'] == '3FGM') & (dfFG['PLAYTYPE'].shift(-1).isin(['FTM','FTMF','FTA']))
    condizione3 = condizione1 & (abs(dfFG['MARKERTIME']-dfFG['MARKERTIME'].shift(-1))<2)
    condizione4 = condizione2 & (abs(dfFG['MARKERTIME']-dfFG['MARKERTIME'].shift(-1))<2)
    dfFG.loc[condizione3,'PLAYTYPE']='2FGF'
    dfFG.loc[condizione4,'PLAYTYPE']='3FGF'
    df.update(dfFG[dfFG['PLAYTYPE'] == '2FGF'])
    df.update(dfFG[dfFG['PLAYTYPE'] == '3FGF'])
    del dfFG
    
    #Seleziono gli "shooting fouls", ovvero i falli che portano ai tiri liberi e che quindi non segnalano una 'play'
    dfF = pd.DataFrame(df.loc[df['PLAYTYPE'].isin(['FTM','FTA','RV','FTMF'])])
    condizione = (dfF['PLAYTYPE'] == 'RV') & (dfF['PLAYTYPE'].shift(-1).isin(['FTM','FTMF','FTA']))
    dfF.loc[condizione,'PLAYTYPE']='SRV'
    df.update(dfF[dfF['PLAYTYPE'] == 'SRV'])
    del dfF
    
    #Seleziono i "falli in attacco" ovvero quei falli che non sono commessi dalla difesa e che determinano un cambio possesso
    dfOF = pd.DataFrame(df.loc[df['PLAYTYPE'].isin(['OF','RV'])])
    condizione1 = (dfOF['PLAYTYPE'] == 'RV') & (dfOF['PLAYTYPE'].shift(1).isin(['OF']))
    condizione2 = (dfOF['PLAYTYPE'] == 'RV') & (dfOF['PLAYTYPE'].shift(-1).isin(['OF']))
    condizione3 = condizione1 & (abs(dfOF['MARKERTIME']-dfOF['MARKERTIME'].shift(1))<2)
    condizione4 = condizione2 & (abs(dfOF['MARKERTIME']-dfOF['MARKERTIME'].shift(-1))<2)
    dfOF.loc[condizione3,'PLAYTYPE']='ORV'
    dfOF.loc[condizione4,'PLAYTYPE']='ORV'
    df.update(dfOF[dfOF['PLAYTYPE'] == 'ORV'])
    del dfOF

    home = find_home(df)
    guest = find_guest(df)

    #Genero l'oggetto di tipo TeamStat
    team_stats = TeamStat(df,home,guest)
    
    #Creo il dataframe relativo alle squadre
    df_team_stats = team_stats.to_dataframe()
    #Arrotondo il risultato alla seconda cifra decimale
    df_team_stats = df_team_stats.applymap(lambda x: round(x, 2))
    #Stampo il risultato
    print(df_team_stats)
        
    #Genero la lista dei nomi dei giocatori presenti durante la partita
    players_names = list(filter(lambda x: x is not None and x != '', df['PLAYER'].unique()))
    player_stats_list = []
    for code in players_names:
        #Genero un oggetto di tipo PlayerStat per ciascun giocatore
        player_stat = PlayerStat(code, df, home, guest)
        #Converto in un dataframe ogni oggetto creato e li inserisco in una lista
        player_stats_list.append(player_stat.to_dataframe())
    
    #Creo il dataframe finale concatenando tutti i dataframe della lista
    all_player_stats = pd.concat(player_stats_list)
    #Ordino il dataframe in base alla squadra di appartenenza
    all_player_stats = all_player_stats.sort_values(by='Team')
    #Arrotondo il risultato alla seconda cifra decimale
    all_player_stats = all_player_stats.round(2)

    #Stampo il risultato
    print (all_player_stats)
    richiesta = input('Premi s per salvare i risultati, oppure premi qualsiasi altro tasto per terminare: ') 
    if richiesta == 's':
        df_team_stats.to_csv(home+'-'+guest+'.dat', sep='\t', index=True)
        all_player_stats.to_csv('players_'+home+'-'+guest+'.dat', sep='\t', index=True)
    
main()