import sqlite3
import cutlet
from ytmusicapi import YTMusic
from thefuzz import fuzz
import time

con = sqlite3.connect('database.db')
cur = con.cursor()

katsu = cutlet.Cutlet()
yt = YTMusic()
song_list = open('songlist.txt', 'r', encoding='utf-8')
base_timestamp = round(time.time() * 1000)

song_count = 0

def insert_into_DB(songID, duration, albumID):
    timestamp = base_timestamp - 2000 * song_count

    search = yt.get_song(songID)
    title = search['videoDetails']['title'].replace('"', "'")
    artistName = search['videoDetails']['author'].replace('"', "'")
    artistID = search['videoDetails']['channelId']
    thumbnail = search['videoDetails']['thumbnail']['thumbnails'][0]['url'] # kill me

    try:
        artist = yt.get_artist(artistID)
        artistImage = artist['thumbnails'][0]['url']
    except:
        return # YTMusic is a very well made library yes yes
    
    if albumID is not None:
        album = yt.get_album(albumID)
        albumTitle = album['title'].replace('"', "'")
        albumImage = album['thumbnails'][0]['url']
        albumYear = album['year']
        shareURL = f"https://music.youtube.com/playlist?list={album['audioPlaylistId']}"

        albumIndex = 0
        for i in album['tracks']:
            if i['title'] is title:
                break
            albumIndex += 1
        

    cur.execute(
        f"""INSERT OR IGNORE INTO Song VALUES("{songID}", "{title}", "{artistName}", "{duration}", "{thumbnail}", "{timestamp}", "0")""")
    cur.execute(
        f"""INSERT OR IGNORE INTO Artist VALUES("{artistID}", "{artistName}", "{artistImage}", "{timestamp}", NULL)""",)
    cur.execute(
        f"""INSERT OR IGNORE INTO SongArtistMap VALUES("{songID}", "{artistID}")""")
    if albumID is not None:
        cur.execute(
            f"""INSERT OR IGNORE INTO Album VALUES("{albumID}", "{albumTitle}", "{albumImage}", "{albumYear}", "{artistName}", "{shareURL}", "{timestamp}", NULL)"""
        )
        cur.execute(
            f"""INSERT OR IGNORE INTO SongAlbumMap VALUES("{songID}", "{albumID}", "{albumIndex}")""")
    con.commit()


for line in song_list.readlines():
    # artist, song title, album title, duration
    song_info = line.split(' | ')
    artist = song_info[0]
    title = song_info[1]

    search = yt.search(f'{title} {artist}', filter='songs')

    # Verifying data to make sure its the correct song
    found_song = False
    for result in search:
        score = max(  # youtube is very cringe and WILL translate to romanji
            fuzz.partial_ratio(katsu.romaji(result['title']), title),
            fuzz.partial_ratio(result['title'], katsu.romaji(title)),
            fuzz.partial_ratio(result['title'], title)
        )
        if score < 90:
            continue

        found_artist = False  # it returns multiple artists, have to check each
        for result_artist in result['artists']:
            score = max( # guess what
                fuzz.partial_ratio(katsu.romaji(result_artist['name']), artist),
                fuzz.partial_ratio(result_artist['name'], katsu.romaji(artist)),
                fuzz.partial_ratio(result_artist['name'], artist)
            )
            if score < 90:
                continue
            found_artist = True
            break
        if not found_artist:
            continue
        # found the song
        
        song_count += 1
        print(f"{result['title']} - {result['videoId']}")

        if result['album'] is not None:
            albumID = result['album']['id']
        else:
            albumID = None
        insert_into_DB(result['videoId'], result['duration'], albumID)
        break
