<?php // content="text/plain; charset=utf-8"
require_once ('../jpgraph/src/jpgraph.php');
require_once ('../jpgraph/src/jpgraph_line.php');
include '/home/lauprellim/connect_mysql/connect-temphumid1.inc';

// use a subquery to get the LAST n entries ordered ascending..
$result = mysqli_query($con,"select * from ( SELECT id, timestamp, temp, humidity FROM climatedata_duq where idLocations='1' order by id DESC LIMIT 672 ) as sub order by id asc");

$data = $result->fetch_all(MYSQLI_ASSOC);

foreach($data as $key => $rowdata) {
	$id[$key] = $rowdata['id'];
	$timestamp[$key] = substr(($rowdata['timestamp']),5, 11);
	$temp[$key] = $rowdata['temp'];
	$humidity[$key] = $rowdata['humidity'];
}

$width = 800; $height = 600;
 
// Create a graph instance
$graph = new Graph($width,$height);
 
// Specify what scale and margins.
// text = text (timestamp) for the X-axis
// int = integer scale for the Y-axis
$graph->SetScale('textint', 10, 70);
$graph->SetMargin(50, 30, 60, 100);

// define TTF font and set graph elements
$graph->SetUserFont('arial.ttf');
$graph->title->SetFont(FF_USERFONT,FS_NORMAL,18);
$graph->subtitle->SetFont(FF_USERFONT,FS_NORMAL, 12);
$graph->xaxis->SetFont(FF_USERFONT,FS_NORMAL,8);
$graph->yaxis->SetFont(FF_USERFONT,FS_NORMAL,8);
$graph->xaxis->title->SetFont(FF_USERFONT,FS_NORMAL,10);
$graph->yaxis->title->SetFont(FF_USERFONT,FS_NORMAL,10);
$graph->legend->SetFont(FF_USERFONT,FS_NORMAL,10);

// Setup a title for the graph
$graph->title->Set('MPSOM - Location 1');
$graph->subtitle->Set('in 15 minute increments');

// Setup titles and X-axis labels
$graph->xaxis->SetTitle('Timestamp (date, time)', 'middle');

// distance from bottom of graph to x-axis label
$graph->xaxis->SetTitleMargin(70);
 
// Setup Y-axis title
$graph->yaxis->title->Set('Temp & Humidity');
$graph->xaxis->SetLabelAngle(90);
$graph->xaxis->SetPos('min');

// put two x-axis ticks per day (@ 96 data points per day)
// make sure that the $timestampLabel array contains exactly the right number of ticks!
// at the current settings we should only have 14 labels
for($i=0; $i<15; $i++) {
	$j = $i*48;
	// fills tick position arrays with values 0=>0, 1=>48, 2=>96, ... 14=>672
	// i.e.:
	// $tickPositions = array(0, 48, 96, 144, 192, 240, 288, 336, 384, 432, 480, 528, 576, 624, 672);
	// $minTickPositions = array(0, 48, 96, 144, 192, 240, 288, 336, 384, 432, 480, 528, 576, 624, 672);
	$tickPositions[$i] = $j;
	$minTickPositions[$i] = $j;
	$timestampLabel[$i] = $timestamp[$j];
}

$graph->xaxis->SetTickPositions($tickPositions, $minTickPositions, $timestampLabel);
$graph->xgrid->Show();

// define and position the graph legend
$graph->legend->SetPos(0.1,0.08,'left','top');
$graph->legend->SetFillColor('#eeeeaa');

// Create the linear plots
$plotTemperature = new LinePlot($temp);
$plotTemperature->SetLegend('Temperature (°C)');
$plotHumidity = new LinePlot($humidity);
$plotHumidity->SetLegend('Humidity (%)');

// Add the plot to the graph
$graph->Add($plotTemperature);
$graph->Add($plotHumidity);

// Display the graph
$graph->Stroke();

?>
