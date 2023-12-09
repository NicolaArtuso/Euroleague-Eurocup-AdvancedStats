import pandas as pd


class TeamStat:
    def __init__(self,df,home,guest):
        self.df = df #Dataframe della partita
        self.home = home #Squadra di casa
        self.guest = guest #Squadra ospite
        self.poss = self.c_poss() #Possessi
        self.sc = self.c_sc() #Plays
        self.points = self.c_points() #Punti
        self.ortg = self.ortg() #Offensive rating
        self.drtg = [self.ortg[1],self.ortg[0]] #Defensive rating
        self.netrtg = [self.ortg[0]-self.ortg[1],self.ortg[1]-self.ortg[0]] #Net rating
        self.astrate = self.ar() #Assist Rate
        self.astto = self.at() #Assist/Palle perse
        self.orebpct = self.c_reb()[0] #Offensive rebound%
        self.drebpct = self.c_reb()[1] #Defensive Rebound %
        self.tovpct = self.c_tov() #Turnover Percentage
        self.eFG = self.efg() #Percentuale effettiva
        self.TS = self.ts() #Percentuale Reale

    def count_stat(self,stat,code): #conta la statistica richiesta, vale solo per team
        dft = self.df.loc[self.df['CODETEAM']== code]
        return len(dft.loc[self.df['PLAYTYPE'].isin(stat)])
        
    def c_poss(self):
     #cambi di possesso segnalati da tiri segnati che portano a una rimessa, palle perse e rimabalzi difensivi 
        home_poss = (self.count_stat(['2FGM','3FGM','FTMF','TO'],self.home)+ 
                     self.count_stat(['D'],self.guest)) 
        guest_poss = (self.count_stat(['2FGM','3FGM','FTMF','TO'],self.guest)+ 
                      self.count_stat(['D'],self.home))
        return [home_poss,guest_poss]
    
    def c_sc(self):
    #plays segnalati dai possessi a cui si aggiungono i rimbalzi in attacco e i falli subiti che non prevedono tiri liberi
        home_sc = self.poss[0] + (self.count_stat(['O','RV'],self.home))
        guest_sc = self.poss[1] + (self.count_stat(['O','RV'],self.guest))
        return [home_sc,guest_sc]
    
    def c_points(self):
        home_points = max(self.df['POINTS_A'])
        guest_points = max(self.df['POINTS_B'])
        return [home_points,guest_points]
    
    def ortg(self):
        if self.poss[0]>0:
            hortg = self.points[0]*100/self.poss[0]
        else: hortg = 0
        if self.poss[1]>0:
            gortg = self.points[1]*100/self.poss[1]
        else: gortg = 0
        return [hortg,gortg]
        
    def c_reb(self):
    #Conteggio dei rimbalzi presi rapportati a quelli disponibili
        rh = [self.count_stat(['O'],self.home),self.count_stat(['D'],self.home)] #rimbalzi in attacco e in difesa della squadra di casa
        rg = [self.count_stat(['O'],self.guest),self.count_stat(['D'],self.guest)] #rimbalzi in attacco e in difesa degli ospiti
        if ((rh[0]+rg[1]) == 0) :
            oreb = 0
        else : 
            oreb = rh[0]/(rh[0]+rg[1]) *100 #attacco home / (attacco home + difesa guest)
        
        if (rh[1]+rg[0] == 0):
            dreb = 0
        else :
            dreb = rh[1]/(rh[1]+rg[0]) * 100 #difesa home / (difesa home + attacco guest)
            
        return [[oreb,100-dreb],[dreb,100-oreb]]
    
    def reb(self):
    #Restituisce i rimbalzi totali disponibili in attacco e difesa per entrambe le squadre
        horebdisp = self.count_stat(['O'],self.home)+self.count_stat(['D'],self.guest)
        hdrebdisp = self.count_stat(['O'],self.guest)+self.count_stat(['D'],self.home)
        return [[horebdisp,hdrebdisp],[hdrebdisp,horebdisp]]
    
    def c_tov(self):
        toh = self.count_stat(['TO'],self.home) * 100 
        tog = self.count_stat(['TO'],self.guest) *100
        return [toh/self.poss[0] if self.poss[0]>0 else 0,tog/self.poss[1] if self.poss[1]>0 else 0]
    
    def ar(self):
        return [self.count_stat(['AS'],self.home)/self.sc[0] *100 if self.sc[0]>0 else 0,
                self.count_stat(['AS'],self.guest)/self.sc[1] *100 if self.sc[1]>0 else 0]
    
        
    def at(self):
        if (self.count_stat(['TO'],self.home) == 0):
            athome = self.count_stat(['AS'],self.home)
        else:                
            athome = self.count_stat(['AS'],self.home)/self.count_stat(['TO'],self.home)
        if (self.count_stat(['TO'],self.guest) == 0):
            atguest = self.count_stat(['AS'],self.guest)
        else: 
            atguest = self.count_stat(['AS'],self.guest)/self.count_stat(['TO'],self.guest)
        return [athome,atguest]
    
    def efg(self):
        tfg = [self.count_stat(['2FGM', '2FGF', '3FGF', '3FGM'], self.home),  #tiri totali messi a segno
               self.count_stat(['2FGM', '2FGF', '3FGF', '3FGM'], self.guest)]
        tp = [0.5*self.count_stat( ['3FGF', '3FGM'], self.home), 0.5*self.count_stat(['3FGF', '3FGM'], self.guest)] #maggior peso per i tiri da 3
        fga = [self.count_stat(['2FGA', '3FGA'], self.home),self.count_stat(['2FGA', '3FGA'], self.guest)] #tiri tentati
        efg_home = (tfg[0] + tp[0]) / (tfg[0]+fga[0]) * 100 if fga[0] > 0 else 0  
        efg_guest = (tfg[1] + tp[1]) / (tfg[1]+fga[1]) * 100 if fga[1] > 0 else 0
        return [efg_home, efg_guest]
    
    def ts(self):
        a = ['2FGM','2FGF','3FGF','3FGM','2FGA','3FGA','FTMF']
        if self.count_stat(a,self.home) >0:
            home = self.points[0]/(2*self.count_stat(a,self.home)) * 100
        else: home = 0
        
        if self.count_stat(a,self.guest) >0:
            guest = self.points[0]/(2*self.count_stat(a,self.guest)) * 100
        else: guest = 0
        return [home,guest]
    
    def to_dataframe(self):
        data = {'Possessions': self.poss,
                'Plays': self.sc,
                'Points': self.points,
                'ORTG': self.ortg,
                'DRTG': self.drtg,
                'NETRTG': self.netrtg,
                'AST RATIO': self.astrate,
                'AST/TO': self.astto,
                'OREB%': self.orebpct,
                'DREB%': self.drebpct,
                'TOV%': self.tovpct,
                'eFG%': self.eFG,
                'TS%': self.TS
                }
        return pd.DataFrame(data, index=[self.home, self.guest])