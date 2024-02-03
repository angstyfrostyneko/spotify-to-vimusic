import sqlite3
import time
import cutlet
from ytmusicapi import YTMusic
from thefuzz import fuzz


def insert_into_db(song_id, duration, album_id, playlist_ids, playlist_positions, is_video=False):
    search = yt.get_song(song_id)
    title = search['videoDetails']['title'].replace('"', "'")
    artist_name = search['videoDetails']['author'].replace('"', "'")
    artist_id = search['videoDetails']['channelId']
    # kill me
    thumbnail = search['videoDetails']['thumbnail']['thumbnails'][0]['url']

    artistImage = None
    try:
        if not is_video:
            artist = yt.get_user(artist_id)
            artistImage = artist['thumbnails'][0]['url']
        else:
            artist = yt.get_user(artist_id)
            artistImage = artist['thumbnails'][0]['url']
    except:
        pass  # YTMusic is a very well made library yes yes

    if album_id is not None:
        album = yt.get_album(album_id)
        album_title = album['title'].replace('"', "'")
        album_image = album['thumbnails'][0]['url']
        album_year = album['year']
        share_url = f"https://music.youtube.com/playlist?list={album['audioPlaylistId']}"

        album_index = 0
        for track in album['tracks']:
            if track['title'] is title:
                break
            album_index += 1

    cur.execute(
        f"""INSERT OR IGNORE INTO Song VALUES("{song_id}", "{title}", "{artist_name}", "{duration}", "{thumbnail}", "{base_timestamp}", "0")""")
    cur.execute(
        f"""INSERT OR IGNORE INTO Artist VALUES("{artist_id}", "{artist_name}", "{artistImage}", "{base_timestamp}", NULL)""")
    cur.execute(
        f"""INSERT OR IGNORE INTO SongArtistMap VALUES("{song_id}", "{artist_id}")""")
    if album_id is not None:
        cur.execute(
            f"""INSERT OR IGNORE INTO Album VALUES("{album_id}", "{album_title}", "{album_image}", "{album_year}", "{artist_name}", "{share_url}", "{base_timestamp}", NULL)"""
        )
        cur.execute(
            f"""INSERT OR IGNORE INTO SongAlbumMap VALUES("{song_id}", "{album_id}", "{album_index}")""")
    # Adds song to playlist 3 (subfavs)
    for (i, playlist_id) in enumerate(playlist_ids):
        cur.execute(
            f"""INSERT OR IGNORE INTO SongPlaylistMap VALUES("{song_id}", "{playlist_id}", "{playlist_positions[i]}")""")
    con.commit()


def find_match(results, title, artist_name):
    for result in results:
        found_title = max(  # youtube is very cringe and WILL translate to romanji
            fuzz.partial_ratio(katsu.romaji(result['title']), title),
            fuzz.partial_ratio(result['title'], katsu.romaji(title)),
            fuzz.partial_ratio(result['title'], title)
        ) > 90

        found_artist = False  # it returns multiple artists, have to check each
        for result_artist in result['artists']:
            artist_score = max(  # guess what
                fuzz.partial_ratio(katsu.romaji(
                    result_artist['name']), artist_name),
                fuzz.partial_ratio(
                    result_artist['name'], katsu.romaji(artist_name)),
                fuzz.partial_ratio(result_artist['name'], artist_name)
            )
            if artist_score > 90:
                found_artist = True
                break

        if found_title and found_artist:
            return result
    return False


def add_song(result, playlist_ids, playlist_positions):
    album_id = result['album']['id'] if 'album' in result and result['album'] is not None else None
    # found_song_count is the position in the playlist
    insert_into_db(result['videoId'], result['duration'],
                   album_id, playlist_ids, playlist_positions)
    for playlist_position in playlist_positions:
        playlist_position += 1


def format_raw_song(raw_title, raw_artist_name):
    return f"\"{raw_title}\" by {raw_artist_name}"


def format_song(title, artists):
    return f"\"{title}\" by " + ", ".join([artist['name'] for artist in artists])

# init -------------------------------------------------------


con = sqlite3.connect('database.db')
cur = con.cursor()

katsu = cutlet.Cutlet()
yt = YTMusic()
song_list = open('songlist.txt', 'r', encoding='utf-8')
base_timestamp = round(time.time() * 1000)


MAX_SEARCH_RESULTS = 10

TOTAL_SONG_COUNT = len(song_list.readlines())  # total songs in songlist.txt
song_list.seek(0)  # reset file pointer so that it can be read again


database_playlists = cur.execute(
    """SELECT id, name FROM Playlist""").fetchall()
database_playlists.insert(
    0, (0, "Favorites"))  # adds default favorites playlist
playlist_ids = []
playlist_positions = []
if len(database_playlists) > 0:
    print("Playlists were detected in the database:")
    for (i, [playlist_id, playlist_name]) in enumerate(database_playlists):
        print("    " + f"({i+1}): {playlist_name}")

    input_playlist_indexes_str = input(
        "Enter matching playlist id(s) separated by commas to add songs to the corresponding playlist(s) (or leave blank to skip): ")
    input_playlist_indexes = [playlist_id.strip()
                          for playlist_id in input_playlist_indexes_str.split(",")]

    if len(input_playlist_indexes_str) > 0:
        for playlist_index in input_playlist_indexes:
            if playlist_index.isdigit():
                playlist_index = int(playlist_index)-1

                if playlist_index < len(database_playlists):
                    playlist_id = database_playlists[playlist_index][0]
                    print(playlist_id)
                    playlist_ids.append(playlist_id)
                    position_result = cur.execute(
                        f"""SELECT position FROM SongPlaylistMap WHERE playlistId = {playlist_id} ORDER BY position DESC LIMIT 1""").fetchone()
                    playlist_positions.append(
                        int(position_result[0]) + 1 if position_result is not None else 0)
    else:
        print("Skipping...")

# main -------------------------------------------------------

print("""Adding songs to vimusic database... If any songs are not found
    during the search, you will be prompted for each song to select a
    matching version from a list of search results after all songs have
    been searched.""")
print()

print("Searching all songs...")

# get all search results for each song in songlist.txt
search_song_count = 0
last_search_timestamp = time.time()
searches = []
for line in song_list.readlines():
    time.sleep(max(0, 1 - last_search_timestamp - time.time()))  # rate limit

    # extracts artist name and song title from songlist.txt
    song_info = line.split(' | ')
    raw_artist_name = song_info[0].strip()
    raw_title = song_info[1].strip()

    print(
        f"Searching for \"{raw_title} {raw_artist_name}\" ({search_song_count}/{TOTAL_SONG_COUNT})")
    searches.append((raw_title, raw_artist_name, (yt.search(
        f'{raw_title} {raw_artist_name}', filter='songs', limit=MAX_SEARCH_RESULTS))))

    search_song_count += 1
    last_search_timestamp = time.time()

print()
print("Done searching")
print()

found_song_count = 0  # found songs
not_found = []
for (search_i, search) in enumerate(searches):
    (raw_title, raw_artist_name, results) = search

    result = find_match(results, raw_title, raw_artist_name)
    if result is not False:
        found_song_count += 1
        add_song(result, playlist_ids, playlist_positions)
        print("Added: " + format_song(result['title'], result['artists']))
    else:
        print("No match found for: " +
              format_raw_song(raw_title, raw_artist_name))
        not_found.append(search_i)

print()
print(f"Added {found_song_count}/{TOTAL_SONG_COUNT} songs to vimusic database")

still_not_found = []
if len(not_found) > 0:
    print()
    continue_input = input(
        "Add by hand songs with no match from the search results (Y/n)? ").lower()

    if continue_input == "y" or len(continue_input) != 1:
        for search_i in not_found:
            (raw_title, raw_artist_name, results) = searches[search_i]

            print("Search results for: " +
                  format_raw_song(raw_title, raw_artist_name))
            for (result_id, result) in enumerate(results):
                print(f"    ({result_id+1}): " +
                      format_song(result['title'], result['artists']))
            result_id = input(
                "Enter the matching song id (leave blank to skip): ")

            if result_id.isdigit():
                result_id = int(result_id)-1
                if result_id < len(results):
                    found_song_count += 1
                    result = results[result_id]
                    add_song(result, playlist_ids, playlist_positions)
                    print("Added: " +
                          format_song(result['title'], result['artists']))
            else:
                print("Skipping...")
                still_not_found.append((raw_title, raw_artist_name))

            print()

if len(still_not_found) > 0:
    print()
    print("Following songs were not found (have a good time matching videos by hand):")
    for (raw_title, raw_artist_name) in still_not_found:
        print("    " + format_raw_song(raw_title, raw_artist_name))
