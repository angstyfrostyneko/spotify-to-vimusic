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


def insert_into_db(song_id, duration, album_id, playlist_position):
    timestamp = base_timestamp - 2000 * found_song_count

    search = yt.get_song(song_id)
    title = search['videoDetails']['title'].replace('"', "'")
    artistName = search['videoDetails']['author'].replace('"', "'")
    artistID = search['videoDetails']['channelId']
    # kill me
    thumbnail = search['videoDetails']['thumbnail']['thumbnails'][0]['url']

    try:
        artist = yt.get_artist(artistID)
        artistImage = artist['thumbnails'][0]['url']
    except:
        return  # YTMusic is a very well made library yes yes

    if album_id is not None:
        album = yt.get_album(album_id)
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
        f"""INSERT OR IGNORE INTO Song VALUES("{song_id}", "{title}", "{artistName}", "{duration}", "{thumbnail}", "{timestamp}", "0")""")
    cur.execute(
        f"""INSERT OR IGNORE INTO Artist VALUES("{artistID}", "{artistName}", "{artistImage}", "{timestamp}", NULL)""")
    cur.execute(
        f"""INSERT OR IGNORE INTO SongArtistMap VALUES("{song_id}", "{artistID}")""")
    if album_id is not None:
        cur.execute(
            f"""INSERT OR IGNORE INTO Album VALUES("{album_id}", "{albumTitle}", "{albumImage}", "{albumYear}", "{artistName}", "{shareURL}", "{timestamp}", NULL)"""
        )
        cur.execute(
            f"""INSERT OR IGNORE INTO SongAlbumMap VALUES("{song_id}", "{album_id}", "{albumIndex}")""")
    # Adds song to playlist 3 (subfavs)
    if PLAYLIST_ID is not None:
        cur.execute(
            f"""INSERT OR IGNORE INTO SongPlaylistMap VALUES("{song_id}", "{3}", "{playlist_position}")""")
    con.commit()

# -----------------------------------------------------------------------------


PLAYLIST_ID = 3  # "None" does not add songs to a playlist
TOTAL_SONG_COUNT = len(song_list.readlines())  # total songs in songlist.txt
song_list.seek(0)  # reset file pointer so that it can be read again

song_count = 0  # searched songs
found_song_count = 0  # found songs

not_found = []

position = 0  # position of the song in the playlist

# if PLAYLIST_ID is not None, get the last song's position to append the new ones
# to the playlist in "the correct order"
if PLAYLIST_ID is not None:
    position_result = cur.execute(
        f"""SELECT * FROM SongPlaylistMap WHERE playlistId = {PLAYLIST_ID} ORDER BY position DESC LIMIT 1""").fetchone()
    if position_result is not None:
        position = int(position_result[2]) + 1

for line in song_list.readlines():
    # artist, song title, album title, duration
    song_info = line.split(' | ')
    artist = song_info[0].strip()
    title = song_info[1].strip()
    song_count += 1

    print(
        f"- Searching \"{title} - {artist}\" ({song_count}/{TOTAL_SONG_COUNT})")

    search = yt.search(f'{title} {artist}', filter='songs')

    found_song = False
    # Verifying data to make sure its the correct song
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
            score = max(  # guess what
                fuzz.partial_ratio(katsu.romaji(
                    result_artist['name']), artist),
                fuzz.partial_ratio(
                    result_artist['name'], katsu.romaji(artist)),
                fuzz.partial_ratio(result_artist['name'], artist)
            )
            if score < 90:
                continue
            found_artist = True
            break
        if not found_artist:
            continue
        # found the song

        found_song = True
        found_song_count += 1

        if result['album'] is not None:
            album_id = result['album']['id']
        else:
            album_id = None
        insert_into_db(result['videoId'],
                       result['duration'], album_id, position)
        position += 1
        break

    if found_song:
        print("Found")
    else:
        print("Not found")
        not_found.append(f"{title} - {artist}")

print(f"Added {found_song_count} songs to vimusic database")

if len(not_found) > 0:
    print("Songs not found:")
    for song in not_found:
        print(f"- {song}")
