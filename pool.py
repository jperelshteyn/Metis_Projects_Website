import sqlite3 

def get_sqldb():
    return sqlite3.connect('data/pool.db')

    
def init_sqldb():
    conn = get_sqldb()
    curs = conn.cursor()
    curs.execute('drop table if exists players')
    curs.execute('drop table if exists games')
    curs.execute('create table players (name text, archived int default 0)')
    curs.execute('''create table games 
                    (winner int, 
                    loser int, 
                    timestamp datetime default CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

class Player:
    
    def save(self, name):   
        conn = get_sqldb()
        curs = conn.cursor()
        curs.execute('insert into players (name) values (?)', (name,))
        self._id = curs.lastrowid
        conn.commit()
        conn.close()
        
    def update(self, old_name, new_name):
        conn = get_sqldb()
        curs = conn.cursor()
        curs.execute('update players set name = ? where name = ?', (new_name, old_name))
        conn.commit()
        conn.close()        


    def get_id(self, name):
        conn = get_sqldb()
        curs = conn.cursor()
        result = curs.execute('select rowid from players where archived = 0 and name = ?', (name,))
        _id = result.fetchone()
        conn.close()
        return _id[0] if _id else None   
    
    def is_duplicate(self, name):
        conn = get_sqldb()
        curs = conn.cursor()
        result = curs.execute('select "exists" from players where archived = 0 and name = ?', (name,))
        exists = result.fetchone()
        conn.close()
        return True if exists else False 
    
    def delete(self, name):
        _id = self.get_id(name)
        if _id:
            conn = get_sqldb()
            curs = conn.cursor()
            curs.execute('update players set archived = 1 where rowid = ?', (_id,))
            conn.commit()
            conn.close()
            return True
        else:
            return False      
    
class Game:
    
    def save(self, winner_name, loser_name):
        winner_id = Player().get_id(winner_name)
        loser_id = Player().get_id(loser_name)
        conn = get_sqldb()
        curs = conn.cursor()
        curs.execute('insert into games (winner, loser) values (?, ?)', (winner_id, loser_id))
        conn.commit()
        conn.close()
        return True        


def get_players():
    conn = get_sqldb()
    curs = conn.cursor()
    players = list(curs.execute('select name from players where archived = 0'))
    conn.close() 
    return [p[0] for p in players]


def get_top_winners(top):
    conn = get_sqldb()
    curs = conn.cursor()
    # winners = list(curs.execute('''
    #                 with 
    #                 win_counts(id, cnt) as
    #                     (select winner as id, count(*) as cnt
    #                     from games
    #                     group by winner),
    #                 loss_counts(id, cnt) as
    #                     (select loser as id, count(*) as cnt
    #                     from games
    #                     group by loser)
    #                 select p.name, 
    #                         w.cnt as win_count, 
    #                         round(100.0 * w.cnt / (w.cnt + coalesce(l.cnt, 0))) as win_percent
    #                 from players p 
    #                     join win_counts w on p.rowid = w.id
    #                     left join loss_counts l on p.rowid = l.id
    #                 where p.archived = 0
    #                 order by win_count desc, win_percent desc
    #                 limit ?''', 
    #              (5,)))
    winners = list(curs.execute('''
                select p.name, 
                        w.cnt as win_count, 
                        round(100.0 * w.cnt / (w.cnt + coalesce(l.cnt, 0))) as win_percent
                from players p 
                    join 
                        (select winner as id, count(*) as cnt
                        from games
                        group by winner) as w 
                    on p.rowid = w.id
                    left join 
                        (select loser as id, count(*) as cnt
                        from games
                        group by loser) as l 
                    on p.rowid = l.id
                where p.archived = 0
                order by win_count desc, win_percent desc
                limit ?''', 
             (top,)))
    conn.close()
    return [{'name': w[0],
             'win_count': w[1],
             'win_percent': w[2]}
            for w in winners]