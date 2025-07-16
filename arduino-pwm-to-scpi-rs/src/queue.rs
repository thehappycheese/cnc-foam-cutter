use core::mem::MaybeUninit;

pub struct FixedQueue<T, const N: usize> {
    buffer: [MaybeUninit<T>; N],
    head: usize,    // Index where next item will be dequeued
    tail: usize,    // Index where next item will be enqueued
    len: usize,     // Current number of items
}

impl<T, const N: usize> FixedQueue<T, N> {
    /// Create a new empty queue
    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            buffer: unsafe { MaybeUninit::uninit().assume_init() },
            head: 0,
            tail: 0,
            len: 0,
        }
    }

    /// Add an item to the back of the queue
    /// If the queue is full, removes the oldest item first
    /// Returns the removed item if one was displaced, None otherwise
    #[inline(always)]
    pub fn enqueue(&mut self, value: T) {
        if self.len == N {
            // Queue is full, remove the oldest item first
            self.head = (self.head + 1) % N;
            self.len -= 1;
        }

        // Now add the new item
        self.buffer[self.tail] = MaybeUninit::new(value);
        self.tail = (self.tail + 1) % N;
        self.len += 1;

    }

    /// Remove and return the item from the front of the queue
    #[inline(always)]
    pub fn dequeue(&mut self) -> Option<T> {
        if self.len == 0 {
            return None;
        }
        let value = unsafe { self.buffer[self.head].assume_init_read() };
        self.head = (self.head + 1) % N;
        self.len -= 1;
        Some(value)
    }

    pub fn space(&self) -> usize {
        N - self.len
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    pub fn is_full(&self) -> bool {
        self.len == N
    }
}