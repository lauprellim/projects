inlets = 2; 
outlets = 1;
var n;
var k;

// all inlets trigger output
function msg_int(int) {
    if (inlet == 1) {
		k=int;
		bang(n, k);
     }
	else {
		n = int;
		bang(n, k);
	}
}

function makeEuclid(n, k) {
	if(k>n) { return 0; }
	var i;
	var num;
	var euclidSet = new Array();
	for(i=0; i<k; i++) {
		num = parseInt ( ( i * n ) / k ) ;
		// it seems impossible to convert floats to ints
		// in max/MSP's version of JS, so have to do it
		// using vexpr int($f1) instead...
		euclidSet.push(num);
	}
	// outlet(1, euclidSet);
	return euclidSet;
}

function bang(n, k) {
	var euclidSet = makeEuclid(n, k);
	outlet(0, euclidSet );
}