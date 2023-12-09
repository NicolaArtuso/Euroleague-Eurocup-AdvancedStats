import pandas as pd
import time
from Team import TeamStat


class PlayerStat:
    def __init__(self,code,df,home,guest): 
        self.code = code  #nome del giocatore 
        self.home = home  #squadra di casa 
        self.guest = guest #squadra ospite
        self.df = self.c_df(df) #dataframe relativo al giocatore in campo
        self.minutes = self.minutes(df) #minuti giocati
        self.team_stat = TeamStat(self.df,self.home,self.guest) #Statistiche di squadra mentre il giocatore è in campo
        self.team = self.find_team() #team del giocatore secondo codice 1=ospite 0=casa
        self.sc = self.c_sc() #"Shooting chances" o "plays" del gicatore
        self.points = self.c_points() #Punti del giocatore
        self.ortg = self.team_points()*100/self.team_stat.poss[self.team]  if self.team_points()>0 else 0 #offensive rating
        self.drtg = self.opp_points()*100/self.team_stat.poss[abs(1-self.team)] if self.opp_points()>0 else 0 #difensive rating
        self.netrtg = self.ortg - self.drtg #net rating
        self.astrate = self.ar() #Rapporto assist/plays
        self.astto = self.at() #rapporto assist/palle perse 
        self.orebpct = self.oreb() #Percentuale di rimbalzi offensivi
        self.drebpct = self.dreb() #Percentuale di rimbalzi difensivi
        self.tovpct = self.c_tov() #Rapporto palle perse/plays
        self.eFG = self.efg() #Percentuale dal campo effettiva
        self.TS = self.ts() #Percentuale reale
        self.usg = self.sc*100/self.team_stat.sc[self.team] if self.sc>0 else 0 #Percentuale di utilizzo
     
    #Funzione che conta le statistiche richieste del giocatore 
    def count_stat(self,stat): 
        dfp = self.df.loc[self.df['PLAYER']== self.code]
        return len(dfp.loc[self.df['PLAYTYPE'].isin(stat)])

    def oreb(self):
        if (self.team_stat.reb()[self.team][0]==0):
            return 0
        return (self.count_stat(['O'])/(self.team_stat.reb()[self.team][0]))
    
    def dreb(self):
        if (self.team_stat.reb()[self.team][1]==0):
            return 0
        return (self.count_stat(['D'])/(self.team_stat.reb()[self.team][1]))
    
    #Fornisce in output due liste: la prima contiene gli indici di riga in cui il giocatore è entrato,
    #la seconda gli indici di riga in cui il giocatore è uscito
    def IN_OUT(self,df):
        playerI = list(df.loc[(df['PLAYTYPE']=='IN') & (df['PLAYER']==self.code)].index) #Entrata del giocatore in campo
        playerO = list(df.loc[(df['PLAYTYPE']=='OUT') & (df['PLAYER']==self.code)].index) #Uscita del giocatore
        if (playerI==[] or (playerO!=[] and playerI[0]>playerO[0])):
            playerI.insert(0,0) #Inserimento dell'indice 0 nella lista delle entrate in caso di partecipazione nel quintetto iniziale
        if (playerO==[] or (playerI!=[] and playerI[-1]>playerO[-1])): 
            playerO.append(len(df)-1) #inserimento di un indice finale in caso di partita terminata in campo
        
        return sorted(playerI), sorted(playerO) 
    
    #Costruisce il datframe della partita mentre il giocatore era in campo
    def c_df(self,df):
        playerI = self.IN_OUT(df)[0]
        playerO = self.IN_OUT(df)[1]
        dfplayer = pd.DataFrame(columns=df.columns)
        for i in range(len(playerI)):
            df_subset = pd.DataFrame(df.loc[playerI[i]:playerO[i]])
            dfplayer = pd.concat([dfplayer,df_subset],axis=0)
        return dfplayer
   #Calcola i minuti di gioco
    def minutes(self,df):
        playerI = self.IN_OUT(df)[0]
        playerO = self.IN_OUT(df)[1]
        total = 0 
        quarters = list(self.df['QUARTER'].unique())
        for i in range(len(playerO)):
            qI = self.df.loc[playerI[i]]['QUARTER']
            qO = self.df.loc[playerO[i]]['QUARTER']
            
            if qI == qO:
                total += self.df.loc[playerI[i]]['MARKERTIME'] - self.df.loc[playerO[i]]['MARKERTIME']
            else:
                total += self.df.loc[playerI[i]]['MARKERTIME']- min(self.df.loc[(self.df['QUARTER']== qI)]['MARKERTIME'])
                total += max(self.df.loc[(self.df['QUARTER']== qO)]['MARKERTIME'])-self.df.loc[playerO[i]]['MARKERTIME']
                total += 600 * (quarters.index(qO) - quarters.index(qI) - 1)

        minuti = int(total // 60)
        secondi = int(total % 60)
        return f"{minuti:02d}:{secondi:02d}"                                                                    
    
    #Restituisce 0 se il giocatore gioca per la squadra di casa, 1 altrimenti
    def find_team(self):
            row = self.df.loc[self.df['PLAYER'] == self.code].iloc[0]
            if row['CODETEAM'] == self.team_stat.home:
                return 0
            return 1
    
    #Calcola le 'shooting chances' o 'plays' del giocatore
    def c_sc(self):
        return (self.count_stat(['2FGA','3FGA','RV','2FGM','3FGM','SRV','TO','AS']))
    
    
    #Calcola i punti del giocatore
    def c_points(self):
        op = self.count_stat(['FTM','FTMF'])
        twp = self.count_stat(['2FGM','2FGF'])
        thp = self.count_stat(['3FGM','3FGF'])
        return (op+2*twp+3*thp)
    
    #Calcola i punti della squadra avversaria
    def opp_points(self):
        op = self.team_stat.count_stat(['FTM','FTMF'],self.opp())
        twp = self.team_stat.count_stat(['2FGM','2FGF'],self.opp())
        thp = self.team_stat.count_stat(['3FGM','3FGF'],self.opp())
        return (op+2*twp+3*thp)
    
    #Calcola i punti della squadra del giocatore
    def team_points(self):
        op = self.team_stat.count_stat(['FTM','FTMF'],self.to_team())
        twp = self.team_stat.count_stat(['2FGM','2FGF'],self.to_team())
        thp = self.team_stat.count_stat(['3FGM','3FGF'],self.to_team())
        return (op+2*twp+3*thp)
    
    #Rapporto Assist/Plays
    def ar(self):
        if self.sc == 0 :
            return 0
        return self.count_stat(['AS'])/self.sc
    #Rapporto Assist/Palle perse
    def at(self):
        if(self.count_stat(['TO']) == 0):
            return None
        return round(self.count_stat(['AS'])/self.count_stat(['TO']),2)
    
    #Rapporto Palle Perse/Plays
    def c_tov(self):
        if self.sc == 0 :
            return 0
        return self.count_stat(['TO'])/self.sc
    
    #Percentuale effettiva dal campo
    def efg(self):
        tfg = self.count_stat(['2FGM', '2FGF', '3FGF', '3FGM'])
        tp = 0.5*self.count_stat(['3FGF', '3FGM'])
        fga = self.count_stat(['2FGA', '3FGA','2FGM', '2FGF', '3FGF', '3FGM'])
        efg = (tfg + tp) / fga * 100 if fga > 0 else 0  # evita divisione per zero
        return efg
    
    #Percentuale reale
    def ts(self):
        a = ['2FGM','2FGF','3FGF','3FGM','2FGA','3FGA','FTMF']
        if self.count_stat(a) == 0:
            return 0
        ts = self.points/(2*self.count_stat(a)) * 100
        return ts
    
    #Trova il codice della squadra del giocatore
    def to_team(self):
        if self.team == 0:
            return self.home
        return self.guest
    
    #Trova il codice della squadra avversaria
    def opp(self):
        if self.team == 1:
            return self.home
        return self.guest
    
    #Conversione di un'istanza dell'oggetto di un dataframe
    def to_dataframe(self):
        data = {
                'Team': [self.to_team()],
                'Minutes':[self.minutes],
                'Plays': [self.sc],
                'Points': [self.points],
                'ORTG': [self.ortg],
                'DRTG': [self.drtg],
                'NETRTG': [self.netrtg],
                'AST rate': [self.astrate],
                'AST/TO': [self.astto],
                'ORB%': [self.orebpct],
                'DRB%': [self.drebpct],
                'TOV%': [self.tovpct],
                'eFG%': [self.eFG],
                'TS%': [self.TS],
                'USG%': [self.usg]}
        return pd.DataFrame(data,index = [self.code])