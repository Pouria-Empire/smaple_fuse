CC=g++
CFLAGS=-Wall -g -D_FILE_OFFSET_BITS=64
LIBS=-lfuse

all: main

main: main.o
	$(CC) $(CFLAGS) -o $@ $^ $(LIBS)

main.o: main.cpp
	$(CC) $(CFLAGS) -c $<

clean:
	rm -f main main.o
