import sqlite3
import time
import cutlet
from ytmusicapi import YTMusic
from thefuzz import fuzz


def insert_into_db(song_id, duration, album_id, playlist_position, is_video = False):
    timestamp = base_timestamp - 2000 * found_song_count

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
            print(artistImage)
        else:
            artist = yt.get_user(artist_id)
            artistImage = artist['thumbnails'][0]['url']
        print(artistImage)
    except:
        pass  # YTMusic is a very well made library yes yes

    if album_id is not None:
        album = yt.get_album(album_id)
        album_title = album['title'].replace('"', "'")
        album_image = album['thumbnails'][0]['url']
        album_year = album['year']
        share_url = f"https://music.youtube.com/playlist?list={album['audioPlaylistId']}"

        album_index = 0
        for i in album['tracks']:
            if i['title'] is title:
                break
            album_index += 1

    cur.execute(
        f"""INSERT OR IGNORE INTO Song VALUES("{song_id}", "{title}", "{artist_name}", "{duration}", "{thumbnail}", "{timestamp}", "0")""")
    cur.execute(
        f"""INSERT OR IGNORE INTO Artist VALUES("{artist_id}", "{artist_name}", "{artistImage}", "{timestamp}", NULL)""")
    cur.execute(
        f"""INSERT OR IGNORE INTO SongArtistMap VALUES("{song_id}", "{artist_id}")""")
    if album_id is not None:
        cur.execute(
            f"""INSERT OR IGNORE INTO Album VALUES("{album_id}", "{album_title}", "{album_image}", "{album_year}", "{artist_name}", "{share_url}", "{timestamp}", NULL)"""
        )
        cur.execute(
            f"""INSERT OR IGNORE INTO SongAlbumMap VALUES("{song_id}", "{album_id}", "{album_index}")""")
    # Adds song to playlist 3 (subfavs)
    if PLAYLIST_ID is not None:
        cur.execute(
            f"""INSERT OR IGNORE INTO SongPlaylistMap VALUES("{song_id}", "{PLAYLIST_ID}", "{playlist_position}")""")
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


def add_song(result, found_song_count):
    album_id = result['album']['id'] if 'album' in result and result['album'] is not None else None
    # found_song_count is the position in the playlist
    insert_into_db(result['videoId'], result['duration'],
                   album_id, found_song_count)


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


PLAYLIST_ID = 1  # "None" does not add songs to a playlist
MAX_SEARCH_RESULTS = 10

TOTAL_SONG_COUNT = len(song_list.readlines())  # total songs in songlist.txt
song_list.seek(0)  # reset file pointer so that it can be read again


# if PLAYLIST_ID is not None, get the last song's position to append the new ones
# to the playlist in "the correct order"
if PLAYLIST_ID is not None:
    position_result = cur.execute(
        f"""SELECT * FROM SongPlaylistMap WHERE playlistId = {PLAYLIST_ID} ORDER BY position DESC LIMIT 1""").fetchone()
    if position_result is not None:
        playlist_position = int(position_result[2]) + 1

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
    time.sleep(max(0, 1 - last_search_timestamp - time.time()))
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
        add_song(result, found_song_count)
        print("Added: " + format_song(result['title'], result['artists']))
    else:
        print("No match found for: " +
              format_raw_song(raw_title, raw_artist_name))
        not_found.append(search_i)

print()
print(f"Added {found_song_count}/{TOTAL_SONG_COUNT} songs to vimusic database")
print()

still_not_found = []
continue_input = input("Add by hand songs with no match (Y/n)? ").lower()
if continue_input == "y" or continue_input == "":
    for search_i in not_found:
        (raw_title, raw_artist_name, results) = searches[search_i]
        print("Search results for: " +
              format_raw_song(raw_title, raw_artist_name))
        for (result_id, result) in enumerate(results):
            print(f"    ({result_id+1}): " +
                  format_song(result['title'], result['artists']))
        result_id = input("Enter song id (leave blank to skip): ")
        if result_id == "" or int(result_id) >= len(results):
            print("Skipping...")
            still_not_found.append((raw_title, raw_artist_name))
        else:
            found_song_count += 1
            result = results[int(result_id)-1]
            add_song(result, found_song_count)
            print("Added: " + format_song(result['title'], result['artists']))
        print()

print()
if len(still_not_found) > 0:
    print("Following songs were not found (have a good time adding them manually):")
    for (raw_title, raw_artist_name) in still_not_found:
        print("    " + format_raw_song(raw_title, raw_artist_name))

# continue_input = input(
#     "Would you like to search videos that would match songs that were not found even after manual search (Y/n)? ").lower()
# if continue_input == "y" or continue_input == "":
#     last_search_timestamp = time.time()
#     for (raw_title, raw_artist_name) in search_video:
#         time.sleep(max(0, 1 - last_search_timestamp - time.time()))
#         print(f"Searching \"{raw_title} {raw_artist_name}\"")
#         results = yt.search(f'{raw_title} {raw_artist_name}',
#                             filter='videos', limit=MAX_SEARCH_RESULTS)
#         last_search_timestamp = time.time()
#         print("Video search results for: " +
#               format_raw_song(raw_title, raw_artist_name))
#         for (result_id, result) in enumerate(results):
#             print(f"    ({result_id+1}): " +
#                   format_song(result['title'], result['artists']))
#         result_id = input("Enter song id (leave blank to skip): ")
#         if result_id == "" or int(result_id) >= len(results):
#             print("Skipping for good...")
#         else:
#             found_song_count += 1
#             result = results[int(result_id)-1]
#             print(result)
#             add_song(result, found_song_count)
#             print("Added: " + format_song(result['title'], result['artists']))
#         print()
