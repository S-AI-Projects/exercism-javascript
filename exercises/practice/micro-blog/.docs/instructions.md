# Instructions

You have identified a gap in the social media market for very very short posts.
Now that Twitter allows 280 character posts, people wanting quick social media updates aren't being served.
You decide to create your own social media network.

To make your product noteworthy, you make it extreme and only allow posts of 5 or less characters.
Any posts of more than 5 characters should be truncated to 5.

To allow your users to express themselves fully, you allow Emoji and other Unicode.

The task is to truncate input strings to 5 characters.

## Text Encodings

Text stored digitally has to be converted to a series of bytes.
There are 3 ways to map characters to bytes in common use.

- **ASCII** can encode English language characters.
  All characters are precisely 1 byte long.
- **UTF-8** is a Unicode text encoding.
  Characters take between 1 and 4 bytes.
- **UTF-16** is a Unicode text encoding.
  Characters are either 2 or 4 bytes long.

UTF-8 and UTF-16 are both Unicode encodings which means they're capable of representing a massive range of characters including:

- Text in most of the world's languages and scripts
- Historic text
- Emoji

UTF-8 and UTF-16 are both variable length encodings, which means that different characters take up different amounts of space.

Consider the letter 'a' and the emoji '😛'.
In UTF-16 the letter takes 2 bytes but the emoji takes 4 bytes.

The trick to this exercise is to use APIs designed around Unicode characters (codepoints) instead of Unicode codeunits.

## JavaScript-specific hint: count visible characters

JavaScript's string `length` counts UTF-16 code units. `Array.from(text)` improves
on that by iterating Unicode code points, but a visible character can contain
more than one code point. For example, `e\u0301` is an `e` followed by a
combining accent. It is one grapheme (what a reader sees as one character), but
two code points. A family emoji joined with zero-width joiners has the same
kind of boundary issue.

The maintained reference uses `Intl.Segmenter` with its default grapheme
granularity. A small contrast shows why:

```javascript
const text = 'e\u0301bcdef';
const graphemes = Array.from(new Intl.Segmenter().segment(text), (part) => part.segment);

graphemes.slice(0, 5).join(''); // 'ébcde' — five graphemes
Array.from(text).slice(0, 5).join(''); // 'ébcd' — five code points, four graphemes
```

For truncation, choose the unit the exercise calls a character. Splitting a
grapheme can leave a combining mark or part of an emoji sequence behind.
