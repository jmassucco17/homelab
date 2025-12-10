s = 'au'

max_length = 1
# Go through all possible start positions
for i in range(len(s) + 1):
    # Go through substrings from that position
    # until we hit one with repeated char
    for j in range(i, len(s)):
        length = j - i + 1
        substring = s[i : j + 1]
        substring_set = set(letter for letter in substring)
        if len(substring_set) != length:
            max_length = max(length - 1, max_length)
            break
        if j == len(s) - 1:
            max_length = max(length, max_length)

print(max_length)
